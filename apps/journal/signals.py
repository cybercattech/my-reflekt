import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Entry, EntryCapture

logger = logging.getLogger(__name__)

# Cache for Redis availability check (avoid repeated connection attempts)
_celery_available = None
_celery_check_time = 0


def is_celery_available():
    """Quick check if Celery/Redis is available (cached for 60 seconds)."""
    import time
    global _celery_available, _celery_check_time

    # Return cached result if checked recently (within 60 seconds)
    now = time.time()
    if _celery_available is not None and (now - _celery_check_time) < 60:
        return _celery_available

    try:
        from django.conf import settings
        import redis
        r = redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1)
        r.ping()
        _celery_available = True
    except Exception:
        _celery_available = False

    _celery_check_time = now
    return _celery_available


def run_sync_analysis(entry):
    """
    Run entry analysis synchronously (fallback when Redis unavailable).
    """
    from apps.analytics.models import EntryAnalysis
    from apps.analytics.services import (
        get_sentiment_score,
        get_sentiment_label,
        classify_mood,
        extract_themes,
        extract_keywords,
    )

    # Run analysis
    sentiment_score = get_sentiment_score(entry.content)
    sentiment_label = get_sentiment_label(sentiment_score)
    # Pass sentiment score to mood classifier for consistency
    detected_mood, confidence, _ = classify_mood(entry.content, sentiment_score)
    themes = extract_themes(entry.content)
    keywords = extract_keywords(entry.content)

    # Generate simple summary
    summary = entry.content[:150] + '...' if len(entry.content) > 150 else entry.content

    # Create or update analysis
    with transaction.atomic():
        analysis, created = EntryAnalysis.objects.update_or_create(
            entry=entry,
            defaults={
                'sentiment_score': sentiment_score,
                'sentiment_label': sentiment_label,
                'detected_mood': detected_mood,
                'mood_confidence': confidence,
                'keywords': keywords,
                'themes': themes,
                'summary': summary,
            }
        )

        # Mark entry as analyzed
        Entry.objects.filter(pk=entry.pk).update(is_analyzed=True)

    logger.info(f"Analyzed entry {entry.id}: {detected_mood} ({sentiment_score:.2f})")


@receiver(post_save, sender=Entry)
def trigger_entry_analysis(sender, instance, created, **kwargs):
    """
    Trigger sentiment analysis after an entry is saved.

    Uses Celery to process asynchronously so saves are fast.
    Falls back to synchronous analysis if Redis/Celery isn't available.
    """
    if not instance.is_analyzed:
        # Only try Celery if Redis is available (fast check)
        if is_celery_available():
            try:
                from apps.analytics.tasks import analyze_entry
                analyze_entry.delay(instance.id)
                return
            except Exception as e:
                logger.warning(f"Celery task failed: {e}")

        # Run synchronously
        try:
            run_sync_analysis(instance)
        except Exception as sync_error:
            logger.error(f"Sync analysis failed: {sync_error}")


def run_sync_capture_processing(capture):
    """
    Process capture synchronously (fallback when Redis unavailable).
    """
    from apps.analytics.services import (
        get_or_create_tracked_book,
        get_or_create_tracked_person,
    )

    user = capture.entry.user

    if capture.capture_type == 'book':
        get_or_create_tracked_book(user, capture)
    elif capture.capture_type == 'person':
        get_or_create_tracked_person(user, capture)

    logger.info(f"Processed capture {capture.id}: {capture.capture_type}")


@receiver(post_save, sender=EntryCapture)
def trigger_capture_processing(sender, instance, created, **kwargs):
    """
    Trigger capture processing after a capture is created.

    Links books/people to tracked entities and updates snapshots.
    """
    if created:
        # Only try Celery if Redis is available (fast check)
        if is_celery_available():
            try:
                from apps.analytics.tasks import process_capture
                process_capture.delay(instance.id)
                return
            except Exception as e:
                logger.warning(f"Celery task failed: {e}")

        # Run synchronously (fast for simple captures)
        try:
            run_sync_capture_processing(instance)
        except Exception as sync_error:
            logger.error(f"Sync capture processing failed: {sync_error}")


@receiver(post_save, sender=Entry)
def trigger_pov_processing(sender, instance, created, **kwargs):
    """
    Process POV blocks after an entry is saved.

    Parses {pov} @username content {/pov} blocks and creates SharedPOV records.
    """
    try:
        from .services.pov import process_entry_povs
        result = process_entry_povs(instance)

        if result['created'] or result['updated'] or result['deleted']:
            logger.info(
                f"POV processing for entry {instance.id}: "
                f"created={result['created']}, updated={result['updated']}, deleted={result['deleted']}"
            )
        if result['errors']:
            logger.warning(f"POV processing errors for entry {instance.id}: {result['errors']}")
    except Exception as e:
        logger.error(f"POV processing failed for entry {instance.id}: {e}")


@receiver(post_save, sender=Entry)
def update_person_mentions(sender, instance, created, **kwargs):
    """
    Track person mentions when an entry is saved.

    Parses [Name](/analytics/people/ID/) links and updates TrackedPerson mention counts.
    Recalculates counts from all entries to ensure accuracy.
    """
    import re
    from apps.analytics.models import TrackedPerson

    try:
        content = instance.content or ''

        # Find all person links: [Name](/analytics/people/123/)
        pattern = r'\[([^\]]+)\]\(/analytics/people/(\d+)/\)'
        matches = re.findall(pattern, content)

        if not matches:
            return

        # Get unique person IDs mentioned in this entry
        person_ids = set(int(match[1]) for match in matches)

        # Get people that belong to this user
        people = TrackedPerson.objects.filter(
            pk__in=person_ids,
            user=instance.user
        )

        entry_date = instance.entry_date

        for person in people:
            # Recalculate mention count by iterating through entries
            # (can't use content__regex because content is encrypted)
            person_pattern = re.compile(rf'\[[^\]]+\]\(/analytics/people/{person.pk}/\)')
            mention_count = 0
            first_date = None
            last_date = None

            for entry in Entry.objects.filter(user=instance.user):
                if entry.content and person_pattern.search(entry.content):
                    mention_count += 1
                    if first_date is None or entry.entry_date < first_date:
                        first_date = entry.entry_date
                    if last_date is None or entry.entry_date > last_date:
                        last_date = entry.entry_date

            person.mention_count = mention_count
            person.first_mention_date = first_date
            person.last_mention_date = last_date
            person.save()

        if matches:
            logger.debug(f"Updated person mentions for entry {instance.id}: {len(people)} people")

    except Exception as e:
        logger.error(f"Person mention tracking failed for entry {instance.id}: {e}")


@receiver(post_save, sender=Entry)
def check_and_award_streak_badges(sender, instance, created, **kwargs):
    """
    Check and award streak badges when an entry is saved.
    Only checks on new entries to avoid excessive processing.
    """
    if not created:
        return

    try:
        from datetime import timedelta
        from django.utils import timezone
        from apps.accounts.models import UserBadge

        user = instance.user
        today = timezone.now().date()

        # Calculate current streak
        all_entry_dates = set(
            Entry.objects.filter(user=user).values_list('entry_date', flat=True)
        )

        current_streak = 0
        check_date = today
        # If no entry today, start from yesterday
        if check_date not in all_entry_dates:
            check_date = today - timedelta(days=1)
        while check_date in all_entry_dates:
            current_streak += 1
            check_date -= timedelta(days=1)

        # Check and award any new badges
        new_badges = UserBadge.check_and_award_badges(user, current_streak)

        if new_badges:
            badge_names = [b['name'] for b in new_badges]
            logger.info(f"Awarded badges to {user.email}: {badge_names}")

    except Exception as e:
        logger.error(f"Badge check failed for entry {instance.id}: {e}")
