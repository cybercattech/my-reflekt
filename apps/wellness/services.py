"""
Wellness correlation and analysis services.
"""
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count


def get_pain_correlations(user, days=90):
    """
    Analyze pain patterns against weather, mood, and other factors.

    Returns dict with correlation insights.
    """
    from .models import PainLog
    from apps.analytics.models import EntryAnalysis

    start_date = timezone.now() - timedelta(days=days)

    pain_logs = PainLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    if not pain_logs.exists():
        return {'insights': [], 'has_data': False}

    insights = []

    # Weather correlation (if we have weather data)
    pain_with_entries = pain_logs.filter(entry__isnull=False).select_related('entry')

    weather_pain = defaultdict(list)
    mood_pain = defaultdict(list)

    for pain in pain_with_entries:
        if hasattr(pain.entry, 'analysis'):
            analysis = pain.entry.analysis
            if analysis.weather_condition:
                weather_pain[analysis.weather_condition].append(pain.intensity)
            if analysis.detected_mood:
                mood_pain[analysis.detected_mood].append(pain.intensity)

    # Calculate weather correlations
    weather_correlations = {}
    for condition, intensities in weather_pain.items():
        if len(intensities) >= 2:
            weather_correlations[condition] = {
                'avg_intensity': round(sum(intensities) / len(intensities), 1),
                'count': len(intensities),
            }

    # Find worst weather for pain
    if weather_correlations:
        worst_weather = max(weather_correlations.items(), key=lambda x: x[1]['avg_intensity'])
        if worst_weather[1]['count'] >= 3:
            insights.append(
                f"Your pain tends to be worse on {worst_weather[0]} days "
                f"(avg intensity: {worst_weather[1]['avg_intensity']}/10)"
            )

    # Mood correlations
    mood_correlations = {}
    for mood, intensities in mood_pain.items():
        if len(intensities) >= 2:
            mood_correlations[mood] = {
                'avg_intensity': round(sum(intensities) / len(intensities), 1),
                'count': len(intensities),
            }

    # Find mood correlation
    if mood_correlations:
        worst_mood = max(mood_correlations.items(), key=lambda x: x[1]['avg_intensity'])
        if worst_mood[1]['count'] >= 3:
            insights.append(
                f"Pain episodes often coincide with {worst_mood[0]} moods"
            )

    # Day of week patterns
    day_counts = defaultdict(int)
    day_intensities = defaultdict(list)
    for pain in pain_logs:
        day = pain.logged_at.strftime('%A')
        day_counts[day] += 1
        day_intensities[day].append(pain.intensity)

    if day_counts:
        worst_day = max(day_counts.items(), key=lambda x: x[1])
        if worst_day[1] >= 3:
            avg_on_worst = sum(day_intensities[worst_day[0]]) / len(day_intensities[worst_day[0]])
            insights.append(
                f"{worst_day[0]}s tend to have more pain episodes "
                f"({worst_day[1]} episodes, avg {avg_on_worst:.1f}/10)"
            )

    return {
        'insights': insights,
        'weather': weather_correlations,
        'mood': mood_correlations,
        'has_data': True,
    }


def get_pain_by_location(user, days=90):
    """Get pain episode counts by body location."""
    from .models import PainLog

    start_date = timezone.now() - timedelta(days=days)

    location_stats = PainLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    ).values('location').annotate(
        count=Count('id'),
        avg_intensity=Avg('intensity')
    ).order_by('-count')

    # Add display names
    location_display = dict(PainLog.LOCATION_CHOICES)
    result = []
    for item in location_stats:
        result.append({
            'location': item['location'],
            'display_name': location_display.get(item['location'], item['location'].title()),
            'count': item['count'],
            'avg_intensity': round(item['avg_intensity'], 1),
        })

    return result


def get_pain_by_day_of_week(user, days=90):
    """Get pain patterns by day of week."""
    from .models import PainLog

    start_date = timezone.now() - timedelta(days=days)

    pain_logs = PainLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = {day: {'count': 0, 'total_intensity': 0} for day in day_order}

    for pain in pain_logs:
        day = pain.logged_at.strftime('%A')
        day_stats[day]['count'] += 1
        day_stats[day]['total_intensity'] += pain.intensity

    result = []
    for day in day_order:
        stats = day_stats[day]
        result.append({
            'day': day,
            'short_day': day[:3],
            'count': stats['count'],
            'avg_intensity': round(stats['total_intensity'] / stats['count'], 1) if stats['count'] > 0 else 0,
        })

    return result


def get_recent_pain_logs(user, limit=20):
    """Get recent pain logs with optional entry data."""
    from .models import PainLog

    return PainLog.objects.filter(
        user=user
    ).select_related('entry').order_by('-logged_at')[:limit]


def update_cycle_prediction(user, person=None):
    """
    Update cycle prediction based on period history.

    Called when a new period_start is logged.
    """
    from .models import CycleLog, CyclePrediction

    # Get last 6 period starts
    period_starts = CycleLog.objects.filter(
        user=user,
        person=person,
        event_type='period_start'
    ).order_by('-log_date')[:6]

    if len(period_starts) < 2:
        return None

    # Calculate cycle lengths
    cycle_lengths = []
    period_lengths = []
    starts = list(period_starts)

    for i in range(len(starts) - 1):
        current_start = starts[i].log_date
        prev_start = starts[i + 1].log_date
        cycle_length = (current_start - prev_start).days
        if 21 <= cycle_length <= 45:  # Valid cycle range
            cycle_lengths.append(cycle_length)

        # Calculate period length if we have end date
        period_end = CycleLog.objects.filter(
            user=user,
            person=person,
            event_type='period_end',
            log_date__gt=prev_start,
            log_date__lt=current_start
        ).first()

        if period_end:
            period_length = (period_end.log_date - prev_start).days
            if 2 <= period_length <= 10:  # Valid period range
                period_lengths.append(period_length)

    if not cycle_lengths:
        return None

    # Calculate averages
    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths))
    avg_period = round(sum(period_lengths) / len(period_lengths)) if period_lengths else 5

    # Predict next start
    last_start = starts[0].log_date
    predicted_start = last_start + timedelta(days=avg_cycle)

    # Update or create prediction
    prediction, _ = CyclePrediction.objects.update_or_create(
        user=user,
        person=person,
        defaults={
            'predicted_start': predicted_start,
            'avg_cycle_length': avg_cycle,
            'avg_period_length': avg_period,
        }
    )

    return prediction


def get_cycle_mood_correlation(user, person=None, days=180):
    """
    Analyze mood patterns across cycle phases.

    Returns mood averages for each phase of the cycle.
    """
    from .models import CycleLog
    from apps.journal.models import Entry
    from apps.analytics.models import EntryAnalysis

    start_date = timezone.now().date() - timedelta(days=days)

    # Get period starts
    period_starts = list(CycleLog.objects.filter(
        user=user,
        person=person,
        event_type='period_start',
        log_date__gte=start_date
    ).values_list('log_date', flat=True).order_by('log_date'))

    if len(period_starts) < 2:
        return None

    # Analyze moods by cycle phase
    phase_sentiments = {
        'menstrual': [],      # Days 1-5
        'follicular': [],     # Days 6-13
        'ovulation': [],      # Days 14-16
        'luteal': [],         # Days 17-28
    }

    for i in range(len(period_starts) - 1):
        cycle_start = period_starts[i]
        cycle_end = period_starts[i + 1]

        # Get entries in this cycle
        entries = Entry.objects.filter(
            user=user,
            entry_date__gte=cycle_start,
            entry_date__lt=cycle_end,
            is_analyzed=True
        ).select_related('analysis')

        for entry in entries:
            if not hasattr(entry, 'analysis'):
                continue

            day_of_cycle = (entry.entry_date - cycle_start).days + 1
            sentiment = entry.analysis.sentiment_score

            if 1 <= day_of_cycle <= 5:
                phase_sentiments['menstrual'].append(sentiment)
            elif 6 <= day_of_cycle <= 13:
                phase_sentiments['follicular'].append(sentiment)
            elif 14 <= day_of_cycle <= 16:
                phase_sentiments['ovulation'].append(sentiment)
            else:
                phase_sentiments['luteal'].append(sentiment)

    # Calculate averages
    results = {}
    for phase, sentiments in phase_sentiments.items():
        if sentiments:
            results[phase] = {
                'avg_sentiment': round(sum(sentiments) / len(sentiments), 3),
                'count': len(sentiments),
            }

    return results


def get_intimacy_patterns(user, days=180):
    """
    Analyze intimacy patterns (discreet).

    Returns frequency stats without explicit details.
    """
    from .models import IntimacyLog

    start_date = timezone.now() - timedelta(days=days)

    logs = IntimacyLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    if not logs.exists():
        return {'has_data': False}

    # Monthly counts
    monthly = defaultdict(int)
    for log in logs:
        month_key = log.logged_at.strftime('%Y-%m')
        monthly[month_key] += 1

    # Average rating if available
    rated_logs = logs.exclude(rating__isnull=True)
    avg_rating = None
    if rated_logs.exists():
        avg_rating = round(rated_logs.aggregate(avg=Avg('rating'))['avg'], 1)

    return {
        'has_data': True,
        'total_count': logs.count(),
        'monthly_counts': dict(monthly),
        'avg_rating': avg_rating,
    }
