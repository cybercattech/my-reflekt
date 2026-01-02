"""
Celery tasks for journal entry analysis.

These tasks run asynchronously after entries are saved.
"""
from celery import shared_task
from django.db import transaction
from collections import Counter


@shared_task
def analyze_entry(entry_id: int):
    """
    Analyze a single journal entry.

    Called automatically when an entry is saved.
    Creates/updates the EntryAnalysis record.

    Note: With per-user encryption, this task needs access to the encryption key
    from cache. If the key is not available, analysis will fail gracefully.
    """
    from apps.journal.models import Entry
    from apps.analytics.models import EntryAnalysis
    from apps.analytics.services import (
        get_sentiment_score,
        get_sentiment_label,
        classify_mood,
        extract_themes,
        extract_keywords,
    )
    from apps.analytics.services.moon import calculate_moon_phase
    from apps.analytics.services.weather import get_weather_data
    from apps.analytics.services.horoscope import get_zodiac_sign
    from apps.journal.services.encryption import (
        UserEncryptionService,
        set_current_encryption_key,
        clear_current_encryption_key,
    )

    try:
        entry = Entry.objects.select_related('user__profile').get(id=entry_id)
    except Entry.DoesNotExist:
        return f"Entry {entry_id} not found"

    # Get encryption key from cache (set during login)
    service = UserEncryptionService(entry.user)
    cached_key = service.get_cached_key()

    if cached_key:
        set_current_encryption_key(cached_key)

    try:
        content = entry.content

        # Check if content was successfully decrypted
        # If no key available, content will be encrypted gibberish
        if not cached_key or content.startswith('gAAAAA'):
            # Content is still encrypted - skip analysis
            clear_current_encryption_key()
            return f"Entry {entry_id}: encryption key not available, skipping analysis"

        # Run analysis
        sentiment_score = get_sentiment_score(content)
        sentiment_label = get_sentiment_label(sentiment_score)
        # Pass sentiment score to mood classifier for consistency
        detected_mood, confidence, _ = classify_mood(content, sentiment_score)
        themes = extract_themes(content)
        keywords = extract_keywords(content)

        # Generate simple summary (first 150 chars for now)
        summary = content[:150] + '...' if len(content) > 150 else content

        # Calculate moon phase for entry date
        moon_phase, moon_illumination = calculate_moon_phase(entry.entry_date)

        # Fetch weather using entry location first, then fall back to profile location
        weather_condition = ''
        weather_description = ''
        weather_location = ''
        temperature = None
        humidity = None
        weather_icon = ''

        profile = entry.user.profile

        # Determine which location to use (entry location takes priority)
        city = entry.city or profile.city
        country_code = entry.country_code or profile.country_code or 'US'

        if city:
            weather_data = get_weather_data(city, country_code)
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
            entry.is_analyzed = True
            entry.save(update_fields=['is_analyzed'])

        # Update monthly snapshot
        update_monthly_snapshot.delay(entry.user_id, entry.entry_date.year, entry.entry_date.month)

        return f"Analyzed entry {entry_id}: {detected_mood} ({sentiment_score:.2f})"

    finally:
        # Always clear the encryption key from thread-local
        clear_current_encryption_key()


@shared_task
def update_monthly_snapshot(user_id: int, year: int, month: int):
    """
    Recalculate monthly aggregates for a user.

    Called after entry analysis completes.
    """
    from django.contrib.auth.models import User
    from apps.journal.models import Entry
    from apps.analytics.models import EntryAnalysis, MonthlySnapshot

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return f"User {user_id} not found"

    # Get all analyzed entries for this month
    entries = Entry.objects.filter(
        user=user,
        entry_date__year=year,
        entry_date__month=month,
        is_analyzed=True
    ).select_related('analysis')

    if not entries.exists():
        return f"No analyzed entries for {year}/{month}"

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
    snapshot, _ = MonthlySnapshot.objects.update_or_create(
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

    return f"Updated snapshot for {user.email} {year}/{month}"


@shared_task
def generate_yearly_review(user_id: int, year: int):
    """
    Generate full year-in-review for a user.

    Called on-demand from dashboard or scheduled for January.
    """
    from django.contrib.auth.models import User
    from apps.journal.models import Entry
    from apps.analytics.models import EntryAnalysis, MonthlySnapshot, YearlyReview

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return f"User {user_id} not found"

    # Get all analyzed entries for the year
    entries = Entry.objects.filter(
        user=user,
        entry_date__year=year,
        is_analyzed=True
    ).select_related('analysis').order_by('entry_date')

    if not entries.exists():
        return f"No analyzed entries for {year}"

    # Basic stats
    total_entries = entries.count()
    total_words = sum(e.word_count for e in entries)

    # Sentiment
    sentiments = [e.analysis.sentiment_score for e in entries if hasattr(e, 'analysis')]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

    # Mood distribution
    moods = [e.analysis.detected_mood for e in entries if hasattr(e, 'analysis')]
    mood_distribution = dict(Counter(moods))
    dominant_mood = Counter(moods).most_common(1)[0][0] if moods else ''

    # Monthly trend
    monthly_snapshots = MonthlySnapshot.objects.filter(
        user=user, year=year
    ).order_by('month')

    monthly_trend = [
        {
            'month': s.month,
            'month_name': s.month_name,
            'sentiment': s.avg_sentiment,
            'mood': s.dominant_mood,
            'entries': s.entry_count,
        }
        for s in monthly_snapshots
    ]

    # Theme analysis
    all_themes = []
    for e in entries:
        if hasattr(e, 'analysis'):
            all_themes.extend(e.analysis.themes)
    top_themes = [theme for theme, _ in Counter(all_themes).most_common(10)]

    # Theme sentiments
    theme_sentiments = {}
    for theme in top_themes[:5]:
        theme_entries = [
            e for e in entries
            if hasattr(e, 'analysis') and theme in e.analysis.themes
        ]
        if theme_entries:
            theme_sentiments[theme] = sum(
                e.analysis.sentiment_score for e in theme_entries
            ) / len(theme_entries)

    # Highlights (top 10 by sentiment)
    sorted_by_sentiment = sorted(
        [e for e in entries if hasattr(e, 'analysis')],
        key=lambda e: e.analysis.sentiment_score,
        reverse=True
    )

    highlights = [
        {
            'id': e.id,
            'date': e.entry_date.isoformat(),
            'sentiment': e.analysis.sentiment_score,
            'mood': e.analysis.detected_mood,
            'preview': e.preview,
        }
        for e in sorted_by_sentiment[:10]
    ]

    lowlights = [
        {
            'id': e.id,
            'date': e.entry_date.isoformat(),
            'sentiment': e.analysis.sentiment_score,
            'mood': e.analysis.detected_mood,
            'preview': e.preview,
        }
        for e in sorted_by_sentiment[-10:]
    ]

    # Generate insights
    insights = []
    if total_entries > 100:
        insights.append(f"You wrote {total_entries} entries this year - impressive consistency!")
    if avg_sentiment > 0.1:
        insights.append("Your overall sentiment was positive this year.")
    elif avg_sentiment < -0.1:
        insights.append("This was a challenging year emotionally.")

    if 'creativity' in top_themes:
        theme_sent = theme_sentiments.get('creativity', 0)
        if theme_sent > 0:
            insights.append("Writing and creativity were positive forces in your life.")

    # Create or update yearly review
    review, _ = YearlyReview.objects.update_or_create(
        user=user,
        year=year,
        defaults={
            'total_entries': total_entries,
            'total_words': total_words,
            'avg_sentiment': avg_sentiment,
            'dominant_mood': dominant_mood,
            'mood_distribution': mood_distribution,
            'monthly_trend': monthly_trend,
            'top_themes': top_themes,
            'theme_sentiments': theme_sentiments,
            'highlights': highlights,
            'lowlights': lowlights,
            'insights': insights,
        }
    )

    return f"Generated yearly review for {user.email} {year}"


@shared_task
def bulk_analyze_entries(user_id: int, entry_ids: list):
    """
    Analyze multiple entries (for imports).

    Chains individual analyze_entry tasks.
    """
    for entry_id in entry_ids:
        analyze_entry.delay(entry_id)

    return f"Queued {len(entry_ids)} entries for analysis"


# =============================================================================
# Capture Processing Tasks
# =============================================================================

@shared_task
def process_capture(capture_id: int):
    """
    Process a new capture - link to tracked entities.

    Called when an EntryCapture is created via slash command.
    Links books/people to their tracked entities.
    """
    from apps.journal.models import EntryCapture
    from apps.analytics.services import (
        get_or_create_tracked_book,
        get_or_create_tracked_person,
    )

    try:
        capture = EntryCapture.objects.select_related('entry').get(id=capture_id)
    except EntryCapture.DoesNotExist:
        return f"Capture {capture_id} not found"

    user = capture.entry.user
    result = None

    # Process based on capture type
    if capture.capture_type == 'book':
        book = get_or_create_tracked_book(user, capture)
        if book:
            result = f"Linked book capture to: {book.title}"
    elif capture.capture_type == 'person':
        person = get_or_create_tracked_person(user, capture)
        if person:
            result = f"Linked person capture to: {person.name}"

    # Update capture snapshot for any capture type
    update_capture_snapshot.delay(
        user.id,
        capture.entry.entry_date.year,
        capture.entry.entry_date.month,
        capture.capture_type
    )

    return result or f"Processed {capture.capture_type} capture {capture_id}"


@shared_task
def update_capture_snapshot(user_id: int, year: int, month: int, capture_type: str):
    """
    Update pre-computed capture aggregates for a month.

    Calculates type-specific stats (e.g., workout duration, ratings).
    """
    from django.contrib.auth.models import User
    from apps.journal.models import EntryCapture
    from apps.analytics.models import CaptureSnapshot

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return f"User {user_id} not found"

    captures = EntryCapture.objects.filter(
        entry__user=user,
        entry__entry_date__year=year,
        entry__entry_date__month=month,
        capture_type=capture_type
    ).select_related('entry')

    count = captures.count()
    data = {}

    # Type-specific aggregations
    if capture_type == 'workout':
        total_duration = 0
        by_type = {}
        by_intensity = {}
        for c in captures:
            duration = c.data.get('duration', 0)
            if isinstance(duration, (int, float)):
                total_duration += duration
            wtype = c.data.get('type', 'other')
            by_type[wtype] = by_type.get(wtype, 0) + 1
            intensity = c.data.get('intensity', 'medium')
            by_intensity[intensity] = by_intensity.get(intensity, 0) + 1
        data = {
            'total_duration': total_duration,
            'avg_duration': round(total_duration / count, 1) if count else 0,
            'by_type': by_type,
            'by_intensity': by_intensity,
        }

    elif capture_type == 'watched':
        by_rating = {}
        by_type = {}
        for c in captures:
            rating = c.data.get('rating')
            if rating:
                by_rating[str(rating)] = by_rating.get(str(rating), 0) + 1
            mtype = c.data.get('type', 'movie')
            by_type[mtype] = by_type.get(mtype, 0) + 1
        data = {'by_rating': by_rating, 'by_type': by_type}

    elif capture_type == 'book':
        by_status = {}
        total_rating = 0
        rating_count = 0
        for c in captures:
            status = c.data.get('status', 'reading')
            by_status[status] = by_status.get(status, 0) + 1
            rating = c.data.get('rating')
            if rating:
                total_rating += rating
                rating_count += 1
        data = {
            'by_status': by_status,
            'avg_rating': round(total_rating / rating_count, 1) if rating_count else None,
        }

    elif capture_type == 'meal':
        by_meal = {}
        for c in captures:
            meal = c.data.get('meal', 'other')
            by_meal[meal] = by_meal.get(meal, 0) + 1
        data = {'by_meal': by_meal}

    elif capture_type == 'person':
        by_context = {}
        unique_people = set()
        for c in captures:
            context = c.data.get('context', 'other')
            if context:
                by_context[context] = by_context.get(context, 0) + 1
            name = c.data.get('name', '')
            if name:
                unique_people.add(name.lower())
        data = {
            'by_context': by_context,
            'unique_people': len(unique_people),
        }

    elif capture_type == 'place':
        by_type = {}
        unique_places = set()
        for c in captures:
            ptype = c.data.get('type', 'other')
            by_type[ptype] = by_type.get(ptype, 0) + 1
            name = c.data.get('name', '')
            if name:
                unique_places.add(name.lower())
        data = {
            'by_type': by_type,
            'unique_places': len(unique_places),
        }

    elif capture_type == 'travel':
        by_mode = {}
        unique_destinations = set()
        for c in captures:
            mode = c.data.get('mode', 'other')
            by_mode[mode] = by_mode.get(mode, 0) + 1
            dest = c.data.get('destination', '')
            if dest:
                unique_destinations.add(dest.lower())
        data = {
            'by_mode': by_mode,
            'unique_destinations': len(unique_destinations),
        }

    elif capture_type == 'gratitude':
        total_items = 0
        for c in captures:
            items = c.data.get('items', [])
            total_items += len(items)
        data = {'total_items': total_items}

    # Create or update snapshot
    CaptureSnapshot.objects.update_or_create(
        user=user,
        year=year,
        month=month,
        capture_type=capture_type,
        defaults={'count': count, 'data': data}
    )

    return f"Updated {capture_type} snapshot for {user.email} {year}/{month}: {count} captures"


@shared_task
def generate_yearly_capture_summary(user_id: int, year: int):
    """
    Generate yearly summary for all capture types.

    Aggregates monthly snapshots into yearly totals.
    """
    from django.contrib.auth.models import User
    from apps.analytics.models import CaptureSnapshot

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return f"User {user_id} not found"

    # Get all monthly snapshots for the year
    snapshots = CaptureSnapshot.objects.filter(
        user=user,
        year=year,
        month__isnull=False
    )

    # Aggregate by capture type
    yearly_data = {}
    for snapshot in snapshots:
        ctype = snapshot.capture_type
        if ctype not in yearly_data:
            yearly_data[ctype] = {
                'count': 0,
                'monthly': []
            }
        yearly_data[ctype]['count'] += snapshot.count
        yearly_data[ctype]['monthly'].append({
            'month': snapshot.month,
            'count': snapshot.count,
            'data': snapshot.data
        })

    # Create yearly snapshots (month=None)
    for capture_type, data in yearly_data.items():
        CaptureSnapshot.objects.update_or_create(
            user=user,
            year=year,
            month=None,
            capture_type=capture_type,
            defaults={'count': data['count'], 'data': data}
        )

    return f"Generated yearly capture summary for {user.email} {year}"
