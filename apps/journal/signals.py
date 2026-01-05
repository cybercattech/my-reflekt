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


def update_monthly_snapshot_sync(user_id, year, month):
    """
    Update monthly snapshot synchronously (fallback when Celery unavailable).

    Recalculates monthly aggregates for a user's entries.
    """
    from django.contrib.auth.models import User
    from apps.analytics.models import EntryAnalysis, MonthlySnapshot
    from collections import Counter

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for monthly snapshot update")
        return

    # Get all analyzed entries for this month
    entries = Entry.objects.filter(
        user=user,
        entry_date__year=year,
        entry_date__month=month,
        is_analyzed=True
    ).select_related('analysis')

    if not entries.exists():
        logger.info(f"No analyzed entries for {user.username} {year}/{month}")
        return

    # Calculate aggregates
    entry_count = entries.count()
    total_words = sum(e.word_count for e in entries)

    # Sentiment
    sentiments = [e.analysis.sentiment_score for e in entries if hasattr(e, 'analysis')]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

    # Mood distribution
    moods = [e.analysis.detected_mood for e in entries if hasattr(e, 'analysis')]
    mood_counts = dict(Counter(moods))
    dominant_mood = Counter(moods).most_common(1)[0][0] if moods else ''

    # Theme aggregation
    all_themes = []
    for e in entries:
        if hasattr(e, 'analysis'):
            all_themes.extend(e.analysis.themes)
    top_themes = [theme for theme, _ in Counter(all_themes).most_common(5)]

    # Find best and worst days
    best_entry = max(entries, key=lambda e: e.analysis.sentiment_score if hasattr(e, 'analysis') else -2)
    worst_entry = min(entries, key=lambda e: e.analysis.sentiment_score if hasattr(e, 'analysis') else 2)

    # Create or update snapshot
    MonthlySnapshot.objects.update_or_create(
        user=user,
        year=year,
        month=month,
        defaults={
            'entry_count': entry_count,
            'total_words': total_words,
            'avg_sentiment': avg_sentiment,
            'dominant_mood': dominant_mood,
            'mood_distribution': mood_counts,
            'top_themes': top_themes,
            'best_day_id': best_entry.id,
            'best_day_sentiment': best_entry.analysis.sentiment_score if hasattr(best_entry, 'analysis') else None,
            'worst_day_id': worst_entry.id,
            'worst_day_sentiment': worst_entry.analysis.sentiment_score if hasattr(worst_entry, 'analysis') else None,
        }
    )

    logger.info(f"Updated monthly snapshot for {user.username} {year}/{month}: {entry_count} entries")


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
    from apps.analytics.services.moon import calculate_moon_phase
    from apps.analytics.services.weather import get_historical_weather
    from apps.analytics.services.horoscope import get_zodiac_sign

    # Get plaintext content (stored before encryption by UserEncryptedTextField.pre_save)
    # Falls back to entry.content if _plaintext_fields not available
    if hasattr(entry, '_plaintext_fields') and 'content' in entry._plaintext_fields:
        content = entry._plaintext_fields['content']
    else:
        content = entry.content

    if not content or content.startswith('gAAAAAB'):
        # Content is still encrypted or empty - skip analysis
        logger.warning(f"Cannot analyze entry {entry.id}: content is encrypted or empty")
        return

    # Run analysis
    sentiment_score = get_sentiment_score(content)
    sentiment_label = get_sentiment_label(sentiment_score)
    # Pass sentiment score to mood classifier for consistency
    detected_mood, confidence, _ = classify_mood(content, sentiment_score)
    themes = extract_themes(content)
    keywords = extract_keywords(content)

    # Generate simple summary from plaintext
    summary = content[:150] + '...' if len(content) > 150 else content

    # Calculate moon phase for entry date
    moon_phase, moon_illumination = calculate_moon_phase(entry.entry_date)

    # Fetch historical weather data
    weather_condition = ''
    weather_description = ''
    weather_location = ''
    temperature = None
    humidity = None
    weather_icon = ''

    profile = entry.user.profile
    city = entry.city or profile.city
    country_code = entry.country_code or profile.country_code or 'US'

    if city:
        weather_data = get_historical_weather(city, entry.entry_date, country_code)
        if weather_data:
            weather_condition = weather_data.get('condition', '')
            weather_description = weather_data.get('description', '')
            temperature = weather_data.get('temperature')
            humidity = weather_data.get('humidity')
            weather_icon = weather_data.get('icon_code', '')
            weather_location = f"{city}, {country_code}"

    # Get zodiac sign if user has birthday and horoscope enabled
    zodiac_sign = ''
    if profile.horoscope_enabled and profile.birthday:
        zodiac_sign = get_zodiac_sign(profile.birthday) or ''

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
                # Moon phase data
                'moon_phase': moon_phase,
                'moon_illumination': moon_illumination,
                # Weather data
                'weather_location': weather_location,
                'weather_condition': weather_condition,
                'weather_description': weather_description,
                'temperature': temperature,
                'humidity': humidity,
                'weather_icon': weather_icon,
                # Zodiac data
                'zodiac_sign': zodiac_sign,
            }
        )

        # Mark entry as analyzed
        Entry.objects.filter(pk=entry.pk).update(is_analyzed=True)

    # Update monthly snapshot synchronously
    update_monthly_snapshot_sync(entry.user.id, entry.entry_date.year, entry.entry_date.month)

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
    Uses plaintext content from _plaintext_fields (before encryption).
    """
    try:
        from .services.pov import process_entry_povs

        # Get plaintext content (stored before encryption by UserEncryptedTextField.pre_save)
        if hasattr(instance, '_plaintext_fields') and 'content' in instance._plaintext_fields:
            plaintext_content = instance._plaintext_fields['content']
        else:
            # Fallback - content might already be decrypted or not encrypted
            plaintext_content = instance.content

        # Skip if content looks encrypted (Fernet tokens start with gAAAA)
        if plaintext_content and plaintext_content.startswith('gAAAAA'):
            logger.warning(f"Skipping POV processing for entry {instance.id}: content is encrypted")
            return

        result = process_entry_povs(instance, plaintext_content=plaintext_content)

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
