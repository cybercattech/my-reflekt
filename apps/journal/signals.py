import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Entry, EntryCapture

logger = logging.getLogger(__name__)


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
    detected_mood, confidence, _ = classify_mood(entry.content)
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
        try:
            # Try async first (faster for user)
            from apps.analytics.tasks import analyze_entry
            analyze_entry.delay(instance.id)
        except Exception as e:
            # Redis/Celery not available - run synchronously
            logger.warning(f"Celery unavailable, running sync analysis: {e}")
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
        try:
            # Try async first
            from apps.analytics.tasks import process_capture
            process_capture.delay(instance.id)
        except Exception as e:
            # Redis/Celery not available - run synchronously
            logger.warning(f"Celery unavailable, running sync capture processing: {e}")
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
            # Update mention dates
            if not person.first_mention_date or entry_date < person.first_mention_date:
                person.first_mention_date = entry_date
            if not person.last_mention_date or entry_date > person.last_mention_date:
                person.last_mention_date = entry_date

            # Recalculate mention count by searching all user's entries
            person_pattern = rf'\[[^\]]+\]\(/analytics/people/{person.pk}/\)'
            mention_count = Entry.objects.filter(
                user=instance.user,
                content__regex=person_pattern
            ).count()
            person.mention_count = mention_count

            person.save()

        if matches:
            logger.debug(f"Updated person mentions for entry {instance.id}: {len(people)} people")

    except Exception as e:
        logger.error(f"Person mention tracking failed for entry {instance.id}: {e}")
