"""
POV (Point of View) Sharing Service.

Handles parsing, validation, and management of shared POV blocks.

Supports two syntax formats:
1. {pov} @username content here {/pov}  - with explicit closing tag
2. {pov} @username content here          - without closing tag (ends at blank line or next {pov})
"""
import re
import hashlib
import logging
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

from apps.accounts.models import Friendship, Profile

logger = logging.getLogger(__name__)

# Regex pattern for POV blocks with closing tag: {pov} @user1 @user2 content {/pov}
# Usernames should be on first line (with or without @ prefix), content starts after newline
POV_PATTERN_CLOSED = re.compile(
    r'\{pov\}\s*([^\n]+?)\s*\n(.*?)\{/pov\}',
    re.DOTALL | re.IGNORECASE
)

# Regex pattern for POV blocks without closing tag: {pov} @user content (until blank line or end)
# Usernames should be on first line, content starts after newline
POV_PATTERN_OPEN = re.compile(
    r'\{pov\}\s*([^\n]+?)\s*\n([^\n]*(?:\n(?!\n|\{pov\})[^\n]*)*)',
    re.IGNORECASE
)

# Regex for extracting usernames (with or without @ prefix)
# Matches words that look like usernames (alphanumeric + underscore)
USERNAME_PATTERN = re.compile(r'@?([\w]+)')


def parse_pov_blocks(content: str) -> list:
    """
    Parse all POV blocks from entry content.

    Supports two formats:
    1. {pov} @user content {/pov}  - explicit closing
    2. {pov} @user content         - ends at blank line or next {pov}

    Returns list of dicts with:
    - usernames: list of mentioned usernames
    - content: the POV content
    - start: start position in original text
    - end: end position in original text
    - raw: the full raw match
    """
    blocks = []
    processed_ranges = []

    # First, find all blocks with closing tags (higher priority)
    for match in POV_PATTERN_CLOSED.finditer(content):
        username_str = match.group(1)
        pov_content = match.group(2).strip()
        usernames = USERNAME_PATTERN.findall(username_str)

        blocks.append({
            'usernames': [u.lower() for u in usernames],
            'content': pov_content,
            'start': match.start(),
            'end': match.end(),
            'raw': match.group(0),
        })
        processed_ranges.append((match.start(), match.end()))

    # Then find blocks without closing tags (skip if overlaps with closed blocks)
    for match in POV_PATTERN_OPEN.finditer(content):
        # Skip if this range overlaps with an already-processed closed block
        start, end = match.start(), match.end()
        overlaps = any(
            (start >= r[0] and start < r[1]) or (end > r[0] and end <= r[1])
            for r in processed_ranges
        )
        if overlaps:
            continue

        username_str = match.group(1)
        pov_content = match.group(2).strip()
        usernames = USERNAME_PATTERN.findall(username_str)

        # Only add if we found valid usernames and content
        if usernames and pov_content:
            blocks.append({
                'usernames': [u.lower() for u in usernames],
                'content': pov_content,
                'start': start,
                'end': end,
                'raw': match.group(0),
            })

    # Sort by position in content
    blocks.sort(key=lambda x: x['start'])

    return blocks


def validate_pov_recipients(author: User, usernames: list) -> tuple:
    """
    Validate that all mentioned users are friends with the author.

    Returns:
    - valid_users: list of User objects who are friends
    - invalid_usernames: list of usernames that are not friends or don't exist
    """
    valid_users = []
    invalid_usernames = []

    for username in usernames:
        try:
            profile = Profile.objects.select_related('user').get(username__iexact=username)
            user = profile.user

            if Friendship.are_friends(author, user):
                valid_users.append(user)
            else:
                invalid_usernames.append(username)
                logger.warning(f"POV recipient @{username} is not friends with {author.email}")
        except Profile.DoesNotExist:
            invalid_usernames.append(username)
            logger.warning(f"POV recipient @{username} does not exist")

    return valid_users, invalid_usernames


def generate_content_hash(content: str, usernames: list) -> str:
    """Generate a hash to identify a POV block."""
    data = f"{','.join(sorted(usernames))}:{content}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


@transaction.atomic
def process_entry_povs(entry) -> dict:
    """
    Process all POV blocks in an entry.

    Called on entry create/update. For each POV block:
    1. Validates recipients are friends
    2. Injects the POV content into each recipient's journal entry for that date
    3. Tracks what was shared to prevent duplicates

    Returns:
    - created: number of new POVs injected
    - updated: number of POVs updated
    - deleted: number of POVs removed
    - errors: list of validation errors
    """
    from ..models import Entry, SharedPOV, SharedPOVRecipient

    result = {
        'created': 0,
        'updated': 0,
        'deleted': 0,
        'errors': [],
    }

    # Parse POV blocks from content
    blocks = parse_pov_blocks(entry.content or '')

    # Get existing POVs for this entry
    existing_povs = {pov.content_hash: pov for pov in entry.shared_povs.all()}
    processed_hashes = set()

    # Get author's username for injection (without @ prefix)
    author_username = entry.user.profile.username or entry.user.email.split('@')[0]

    for idx, block in enumerate(blocks):
        # Validate recipients
        valid_users, invalid_users = validate_pov_recipients(entry.user, block['usernames'])

        if invalid_users:
            result['errors'].append(
                f"POV block {idx + 1}: @{', @'.join(invalid_users)} are not friends or don't exist"
            )

        if not valid_users:
            continue  # Skip POV if no valid recipients

        # Generate hash (includes author to make it unique per sender)
        content_hash = generate_content_hash(
            f"{entry.user.id}:{block['content']}",
            block['usernames']
        )
        processed_hashes.add(content_hash)

        is_new = content_hash not in existing_povs

        if is_new:
            # Create SharedPOV record to track this
            pov = SharedPOV.objects.create(
                entry=entry,
                author=entry.user,
                content=block['content'],
                content_hash=content_hash,
                position_index=idx,
            )

            # Inject into each recipient's journal
            for user in valid_users:
                _inject_pov_into_journal(
                    recipient=user,
                    author=entry.user,
                    author_username=author_username,
                    content=block['content'],
                    entry_date=entry.entry_date,
                    pov=pov,
                )
                SharedPOVRecipient.objects.create(pov=pov, user=user)

            # Queue email notifications
            _queue_pov_notifications(pov)
            result['created'] += 1

        else:
            # POV already exists - check if content changed
            pov = existing_povs[content_hash]
            if pov.content != block['content']:
                pov.content = block['content']
                pov.position_index = idx
                pov.save()
                result['updated'] += 1

    # Handle deleted POVs (blocks removed from entry)
    for content_hash, pov in existing_povs.items():
        if content_hash not in processed_hashes:
            # Note: We don't remove injected content from recipient's entries
            # as that would be destructive. We just mark the POV as deleted.
            pov.delete()
            result['deleted'] += 1

    # Note: We keep the POV blocks in the author's entry so they can see what was shared
    # The blocks are rendered as styled "Shared with @username" admonitions
    # Only the recipient gets the injected version

    return result


def _remove_pov_blocks_from_entry(entry, blocks):
    """
    Remove POV blocks from the author's entry after processing.

    The POV content has been sent to recipients, so we remove it from
    the author's entry to avoid duplication.
    """
    from ..models import Entry

    content = entry.content or ''

    # Remove blocks in reverse order to preserve positions
    for block in reversed(blocks):
        # Remove the raw POV block from content
        content = content[:block['start']] + content[block['end']:]

    # Clean up any excessive blank lines
    import re
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    # Update entry without triggering signals
    Entry.objects.filter(pk=entry.pk).update(
        content=content,
        word_count=len(content.split()) if content else 0
    )


def _inject_pov_into_journal(recipient, author, author_username: str, content: str, entry_date, pov):
    """
    Inject POV content into recipient's journal entry for the given date.

    Creates a new entry if none exists, or appends to existing entry.
    Uses ```pov @username format which renders as a styled block.
    Note: We use 'pov' without braces to avoid matching the {pov}...{/pov} parsing regex.
    """
    from ..models import Entry

    # Format the POV block for injection
    # IMPORTANT: Use 'pov' without braces to avoid the {pov} regex pattern matching it
    pov_block = f"\n\n```pov @{author_username}\n{content}\n```\n"

    # Find or create recipient's entry for this date
    recipient_entry, created = Entry.objects.get_or_create(
        user=recipient,
        entry_date=entry_date,
        defaults={
            'title': '',
            'content': pov_block.strip(),
        }
    )

    if not created:
        # Append to existing entry (if not already there)
        # Use a marker to prevent duplicate injection
        marker = f"<!-- pov:{pov.content_hash} -->"

        if marker not in recipient_entry.content:
            recipient_entry.content = (recipient_entry.content or '') + pov_block + marker
            # Save without triggering signals to avoid recursion
            Entry.objects.filter(pk=recipient_entry.pk).update(
                content=recipient_entry.content,
                word_count=len(recipient_entry.content.split())
            )

    logger.info(f"Injected POV from {author.email} into {recipient.email}'s entry for {entry_date}")


def _queue_pov_notifications(pov):
    """Queue notifications for all POV recipients."""
    try:
        from ..tasks import send_pov_notification
        send_pov_notification.delay(pov.id)
    except Exception as e:
        logger.warning(f"Could not queue POV notification: {e}")


def _queue_pov_notification_for_user(pov, user: User):
    """Queue notification for a specific POV recipient."""
    try:
        from ..tasks import send_pov_notification_to_user
        send_pov_notification_to_user.delay(pov.id, user.id)
    except Exception as e:
        logger.warning(f"Could not queue POV notification for user: {e}")


def get_shared_povs_for_user(user: User, unread_only: bool = False):
    """Get all POVs shared with a user."""
    from ..models import SharedPOVRecipient

    queryset = SharedPOVRecipient.objects.filter(user=user).select_related(
        'pov',
        'pov__entry',
        'pov__author',
        'pov__author__profile'
    ).order_by('-pov__created_at')

    if unread_only:
        queryset = queryset.filter(is_read=False)

    return queryset


def get_unread_pov_count(user: User) -> int:
    """Get count of unread POVs for a user."""
    from ..models import SharedPOVRecipient

    return SharedPOVRecipient.objects.filter(
        user=user,
        is_read=False
    ).count()


def mark_pov_as_read(pov_id: int, user: User) -> bool:
    """Mark a POV as read for a user."""
    from ..models import SharedPOVRecipient

    updated = SharedPOVRecipient.objects.filter(
        pov_id=pov_id,
        user=user,
        is_read=False
    ).update(is_read=True, read_at=django_timezone.now())

    return updated > 0


def can_view_pov(pov, user: User) -> bool:
    """Check if a user can view a POV."""
    if pov.author == user:
        return True
    return pov.recipients.filter(user=user).exists()


def can_reply_to_pov(pov, user: User) -> bool:
    """Check if a user can reply to a POV."""
    return can_view_pov(pov, user)


@transaction.atomic
def create_pov_reply(pov, author: User, content: str):
    """Create a reply to a POV."""
    from ..models import POVReply

    if not can_reply_to_pov(pov, author):
        raise PermissionError("You don't have permission to reply to this POV")

    reply = POVReply.objects.create(
        pov=pov,
        author=author,
        content=content
    )

    # Notify other participants
    _queue_reply_notifications(reply)

    return reply


def _queue_reply_notifications(reply):
    """Queue notifications for POV reply."""
    try:
        from ..tasks import send_pov_reply_notification
        send_pov_reply_notification.delay(reply.id)
    except Exception as e:
        logger.warning(f"Could not queue POV reply notification: {e}")


@transaction.atomic
def delete_pov_for_recipient(pov_id: int, user: User) -> bool:
    """
    Delete a POV for a specific recipient.

    This removes the POV content from the recipient's journal entry
    and deletes the SharedPOVRecipient record.

    Returns True if successful, False if POV not found or user not a recipient.
    """
    from ..models import Entry, SharedPOV, SharedPOVRecipient

    try:
        recipient_record = SharedPOVRecipient.objects.select_related('pov').get(
            pov_id=pov_id,
            user=user
        )
    except SharedPOVRecipient.DoesNotExist:
        return False

    pov = recipient_record.pov

    # Find the recipient's entry for the POV date
    try:
        recipient_entry = Entry.objects.get(
            user=user,
            entry_date=pov.entry.entry_date
        )

        # Remove the POV block from the entry content
        # The injected format is: ```pov @username\ncontent\n```
        author_username = pov.author.profile.username or pov.author.email.split('@')[0]

        # Pattern to match the injected POV block (using 'pov' without braces)
        import re
        pov_pattern = re.compile(
            r'\n*```pov\s*@' + re.escape(author_username) + r'\s*\n' +
            re.escape(pov.content) + r'\n```\n*',
            re.DOTALL
        )

        # Also remove the marker comment if present
        marker = f"<!-- pov:{pov.content_hash} -->"

        new_content = pov_pattern.sub('', recipient_entry.content or '')
        new_content = new_content.replace(marker, '')

        # Clean up any excessive blank lines
        new_content = re.sub(r'\n{3,}', '\n\n', new_content).strip()

        # Update the entry without triggering signals
        Entry.objects.filter(pk=recipient_entry.pk).update(
            content=new_content,
            word_count=len(new_content.split()) if new_content else 0
        )

        logger.info(f"Removed POV content from {user.email}'s entry for {pov.entry.entry_date}")

    except Entry.DoesNotExist:
        # Entry doesn't exist, nothing to clean up
        pass

    # Delete the recipient record
    recipient_record.delete()
    logger.info(f"Deleted POV recipient record for user {user.email}, POV {pov_id}")

    return True
