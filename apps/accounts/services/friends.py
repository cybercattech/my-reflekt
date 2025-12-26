"""
Friend request and friendship management services.

Business logic for friend operations, separated from views.
"""
import logging
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone

from ..models import Friendship, FriendRequest, Invitation, Profile

logger = logging.getLogger(__name__)


class FriendshipError(Exception):
    """Custom exception for friendship operations."""
    pass


def get_friendship_status(user, other_user):
    """
    Get the relationship status between two users.

    Returns:
        dict: {
            'status': 'none' | 'friends' | 'request_sent' | 'request_received' | 'self',
            'friendship': Friendship or None,
            'friend_request': FriendRequest or None
        }
    """
    if user == other_user:
        return {'status': 'self', 'friendship': None, 'friend_request': None}

    # Check if already friends
    if Friendship.are_friends(user, other_user):
        if user.id < other_user.id:
            friendship = Friendship.objects.get(user1=user, user2=other_user)
        else:
            friendship = Friendship.objects.get(user1=other_user, user2=user)
        return {'status': 'friends', 'friendship': friendship, 'friend_request': None}

    # Check for pending request sent by user
    sent_request = FriendRequest.objects.filter(
        sender=user, recipient=other_user, status='pending'
    ).first()
    if sent_request:
        return {'status': 'request_sent', 'friendship': None, 'friend_request': sent_request}

    # Check for pending request received by user
    received_request = FriendRequest.objects.filter(
        sender=other_user, recipient=user, status='pending'
    ).first()
    if received_request:
        return {'status': 'request_received', 'friendship': None, 'friend_request': received_request}

    return {'status': 'none', 'friendship': None, 'friend_request': None}


def send_friend_request(sender, recipient_email, message=''):
    """
    Send a friend request by email.

    If recipient exists: create FriendRequest
    If recipient doesn't exist: create Invitation and queue email

    Args:
        sender: User sending the request
        recipient_email: Email address of recipient
        message: Optional personal message

    Returns:
        tuple: (request_type, object)
            - ('friend_request', FriendRequest) for existing users
            - ('invitation', Invitation) for non-users

    Raises:
        FriendshipError: For validation errors
    """
    recipient_email = recipient_email.lower().strip()

    # Can't friend yourself
    if sender.email.lower() == recipient_email:
        raise FriendshipError("You cannot send a friend request to yourself.")

    # Check if user exists
    try:
        recipient = User.objects.get(email__iexact=recipient_email)
    except User.DoesNotExist:
        recipient = None

    if recipient:
        # Check if already friends
        if Friendship.are_friends(sender, recipient):
            raise FriendshipError("You are already friends with this user.")

        # Check for existing pending request
        existing = FriendRequest.objects.filter(
            sender=sender, recipient=recipient, status='pending'
        ).exists()
        if existing:
            raise FriendshipError("You already have a pending request to this user.")

        # Check for reverse request (they sent one to you)
        reverse = FriendRequest.objects.filter(
            sender=recipient, recipient=sender, status='pending'
        ).first()
        if reverse:
            # Auto-accept if they already sent a request
            return accept_friend_request(sender, reverse.id)

        # Create friend request
        friend_request = FriendRequest.objects.create(
            sender=sender,
            recipient=recipient,
            message=message[:200] if message else ''
        )

        # Queue notification email
        try:
            from ..tasks import send_friend_request_email
            send_friend_request_email.delay(friend_request.id)
        except Exception as e:
            logger.warning(f"Could not queue friend request email: {e}")

        logger.info(f"Friend request sent: {sender.email} -> {recipient.email}")
        return ('friend_request', friend_request)

    else:
        # Check for existing pending invitation
        existing = Invitation.objects.filter(
            sender=sender, email=recipient_email, status='pending'
        ).first()
        if existing and not existing.is_expired:
            raise FriendshipError("You already have a pending invitation to this email.")

        # Create invitation
        invitation = Invitation.objects.create(
            sender=sender,
            email=recipient_email,
            message=message[:200] if message else ''
        )

        # Queue invitation email
        try:
            from ..tasks import send_invitation_email
            send_invitation_email.delay(invitation.id)
        except Exception as e:
            logger.warning(f"Could not queue invitation email: {e}")

        logger.info(f"Invitation sent: {sender.email} -> {recipient_email}")
        return ('invitation', invitation)


@transaction.atomic
def accept_friend_request(user, request_id):
    """
    Accept a friend request.

    Creates bidirectional Friendship and updates request status.
    """
    try:
        friend_request = FriendRequest.objects.select_for_update().get(
            id=request_id,
            recipient=user,
            status='pending'
        )
    except FriendRequest.DoesNotExist:
        raise FriendshipError("Friend request not found or already processed.")

    # Create friendship
    friendship = Friendship.create_friendship(user, friend_request.sender)

    # Update request
    friend_request.status = 'accepted'
    friend_request.responded_at = timezone.now()
    friend_request.save()

    # Notify sender
    try:
        from ..tasks import send_friend_request_accepted_email
        send_friend_request_accepted_email.delay(friend_request.id)
    except Exception as e:
        logger.warning(f"Could not queue acceptance email: {e}")

    logger.info(f"Friend request accepted: {friend_request.sender.email} <-> {user.email}")
    return ('friendship', friendship)


@transaction.atomic
def deny_friend_request(user, request_id):
    """Deny a friend request."""
    try:
        friend_request = FriendRequest.objects.select_for_update().get(
            id=request_id,
            recipient=user,
            status='pending'
        )
    except FriendRequest.DoesNotExist:
        raise FriendshipError("Friend request not found or already processed.")

    friend_request.status = 'denied'
    friend_request.responded_at = timezone.now()
    friend_request.save()

    logger.info(f"Friend request denied: {friend_request.sender.email} -> {user.email}")
    return friend_request


def cancel_friend_request(user, request_id):
    """Cancel a pending friend request sent by user."""
    try:
        friend_request = FriendRequest.objects.get(
            id=request_id,
            sender=user,
            status='pending'
        )
    except FriendRequest.DoesNotExist:
        raise FriendshipError("Friend request not found or already processed.")

    friend_request.status = 'cancelled'
    friend_request.responded_at = timezone.now()
    friend_request.save()

    logger.info(f"Friend request cancelled: {user.email} -> {friend_request.recipient.email}")
    return friend_request


@transaction.atomic
def unfriend(user, friend_id):
    """Remove a friendship."""
    try:
        friend = User.objects.get(id=friend_id)
    except User.DoesNotExist:
        raise FriendshipError("User not found.")

    if not Friendship.are_friends(user, friend):
        raise FriendshipError("You are not friends with this user.")

    # Delete friendship (ordering matters)
    if user.id < friend.id:
        Friendship.objects.filter(user1=user, user2=friend).delete()
    else:
        Friendship.objects.filter(user1=friend, user2=user).delete()

    logger.info(f"Friendship removed: {user.email} <-> {friend.email}")
    return True


@transaction.atomic
def accept_invitation(user, invitation_id):
    """
    Accept an invitation (called by newly signed-up user).

    Creates friendship with the inviter.
    """
    try:
        invitation = Invitation.objects.select_for_update().get(
            id=invitation_id,
            recipient=user,
            status='signed_up'
        )
    except Invitation.DoesNotExist:
        raise FriendshipError("Invitation not found or already processed.")

    if invitation.is_expired:
        invitation.status = 'expired'
        invitation.save()
        raise FriendshipError("This invitation has expired.")

    # Create friendship
    friendship = Friendship.create_friendship(user, invitation.sender)

    # Update invitation
    invitation.status = 'accepted'
    invitation.responded_at = timezone.now()
    invitation.save()

    # Notify inviter
    try:
        from ..tasks import send_invitation_accepted_email
        send_invitation_accepted_email.delay(invitation.id)
    except Exception as e:
        logger.warning(f"Could not queue invitation accepted email: {e}")

    logger.info(f"Invitation accepted: {user.email} accepted invite from {invitation.sender.email}")
    return friendship


def deny_invitation(user, invitation_id):
    """Deny an invitation."""
    try:
        invitation = Invitation.objects.get(
            id=invitation_id,
            recipient=user,
            status='signed_up'
        )
    except Invitation.DoesNotExist:
        raise FriendshipError("Invitation not found or already processed.")

    invitation.status = 'denied'
    invitation.responded_at = timezone.now()
    invitation.save()

    logger.info(f"Invitation denied: {user.email} denied invite from {invitation.sender.email}")
    return invitation


def get_pending_friend_requests(user):
    """Get all pending friend requests for a user."""
    return {
        'received': FriendRequest.objects.filter(
            recipient=user, status='pending'
        ).select_related('sender', 'sender__profile').order_by('-created_at'),
        'sent': FriendRequest.objects.filter(
            sender=user, status='pending'
        ).select_related('recipient', 'recipient__profile').order_by('-created_at'),
    }


def get_pending_invitations(user):
    """Get pending invitations for a user (both sent and received)."""
    return {
        'sent': Invitation.objects.filter(
            sender=user, status='pending'
        ).order_by('-created_at'),
        'received': Invitation.objects.filter(
            recipient=user, status='signed_up'
        ).select_related('sender', 'sender__profile').order_by('-created_at'),
    }


def search_users_by_username(query, exclude_user=None, limit=10):
    """
    Search for users by username prefix.

    Used for autocomplete in friend request form.
    """
    query = query.strip().lstrip('@').lower()
    if len(query) < 2:
        return []

    profiles = Profile.objects.filter(
        username__icontains=query
    ).select_related('user')[:limit]

    if exclude_user:
        profiles = profiles.exclude(user=exclude_user)

    return profiles
