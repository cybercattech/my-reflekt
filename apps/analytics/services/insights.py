"""
Insight generation service for correlating mood with environmental factors.

Generates correlations between mood/sentiment and:
- Moon phases
- Weather conditions
- Zodiac sign periods
"""
from collections import defaultdict
from typing import Dict, List, Optional
from django.db.models import Avg, Count
from django.contrib.auth.models import User

from apps.analytics.services.moon import MOON_PHASE_DISPLAY, MOON_PHASE_ICONS
from apps.analytics.services.horoscope import ZODIAC_DISPLAY, ZODIAC_SYMBOLS, ELEMENT_COLORS, get_zodiac_element
from apps.analytics.services.weather import WEATHER_DISPLAY


def generate_moon_correlation(user: User, days: int = 90) -> Dict:
    """
    Correlate mood with moon phases over the specified period.

    Returns aggregated sentiment and mood counts by moon phase.
    """
    from apps.journal.models import Entry
    from apps.analytics.models import EntryAnalysis
    from datetime import timedelta
    from django.utils import timezone

    start_date = timezone.now().date() - timedelta(days=days)

    # Get entries with moon phase data
    entries = Entry.objects.filter(
        user=user,
        entry_date__gte=start_date,
        is_analyzed=True
    ).select_related('analysis').exclude(
        analysis__moon_phase=''
    )

    # Aggregate by moon phase
    phase_data = defaultdict(lambda: {
        'count': 0,
        'total_sentiment': 0.0,
        'moods': defaultdict(int),
    })

    for entry in entries:
        if not hasattr(entry, 'analysis'):
            continue

        phase = entry.analysis.moon_phase
        if not phase:
            continue

        phase_data[phase]['count'] += 1
        phase_data[phase]['total_sentiment'] += entry.analysis.sentiment_score
        phase_data[phase]['moods'][entry.analysis.detected_mood] += 1

    # Calculate averages and format results
    results = []
    for phase, data in phase_data.items():
        if data['count'] == 0:
            continue

        avg_sentiment = data['total_sentiment'] / data['count']
        dominant_mood = max(data['moods'].items(), key=lambda x: x[1])[0] if data['moods'] else ''

        results.append({
            'phase': phase,
            'display_name': MOON_PHASE_DISPLAY.get(phase, phase.replace('_', ' ').title()),
            'icon': MOON_PHASE_ICONS.get(phase, 'bi-moon'),
            'count': data['count'],
            'avg_sentiment': round(avg_sentiment, 3),
            'sentiment_label': 'positive' if avg_sentiment > 0.05 else ('negative' if avg_sentiment < -0.05 else 'neutral'),
            'dominant_mood': dominant_mood,
        })

    # Sort by average sentiment
    results.sort(key=lambda x: x['avg_sentiment'], reverse=True)

    # Generate insights
    insights = []
    best_mood_by_phase = {}

    if results:
        best_phase = results[0]
        worst_phase = results[-1]

        # Get the most common mood for each phase
        for phase_result in results:
            phase = phase_result['phase']
            # Find data for this phase
            phase_info = phase_data.get(phase, {})
            if phase_info.get('moods'):
                best_mood = max(phase_info['moods'].items(), key=lambda x: x[1])
                best_mood_by_phase[phase] = best_mood[0]

        # Full moon specific insights
        full_moon_data = next((r for r in results if r['phase'] == 'full_moon'), None)
        if full_moon_data and full_moon_data['count'] >= 2:
            full_moon_mood = best_mood_by_phase.get('full_moon', '')
            if full_moon_data['avg_sentiment'] > 0.1:
                mood_text = f"feeling {full_moon_mood}" if full_moon_mood else "more positive"
                insights.append(
                    f"🌕 Your writing skews towards {mood_text} during the full moon"
                )
            elif full_moon_data['avg_sentiment'] < -0.1:
                insights.append(
                    f"🌕 Full moon phases tend to bring more introspective, reflective writing"
                )
            else:
                # Neutral sentiment
                mood_text = f"feeling {full_moon_mood}" if full_moon_mood else "balanced"
                insights.append(
                    f"🌕 Your writing skews towards {mood_text} during the full moon"
                )

        # New moon insights
        new_moon_data = next((r for r in results if r['phase'] == 'new_moon'), None)
        if new_moon_data and new_moon_data['count'] >= 2:
            new_moon_mood = best_mood_by_phase.get('new_moon', '')
            if new_moon_data['avg_sentiment'] > 0.1:
                insights.append(
                    f"🌑 New moon phases inspire {new_moon_mood if new_moon_mood else 'positive'} energy in your entries"
                )
            elif new_moon_data['avg_sentiment'] < -0.1:
                insights.append(
                    f"🌑 New moon phases seem to bring more contemplative, introspective moods"
                )
            else:
                # Neutral - still generate insight
                mood_text = f"{new_moon_mood}" if new_moon_mood else "reflective"
                insights.append(
                    f"🌑 New moon writing tends toward {mood_text} themes"
                )

        # General best phase
        if best_phase['avg_sentiment'] > 0.1 and best_phase['phase'] not in ['full_moon', 'new_moon']:
            best_mood = best_mood_by_phase.get(best_phase['phase'], '')
            mood_text = f" and {best_mood}" if best_mood else ""
            insights.append(
                f"✨ You feel most positive{mood_text} during {best_phase['display_name']} phases"
            )

        # Worst phase (if significantly different)
        if worst_phase['avg_sentiment'] < -0.05 and best_phase != worst_phase:
            sentiment_diff = best_phase['avg_sentiment'] - worst_phase['avg_sentiment']
            if sentiment_diff > 0.2:  # Significant difference
                insights.append(
                    f"🌙 {worst_phase['display_name']} phases seem to bring more contemplative moods"
                )

        # Waxing vs Waning comparison
        waxing_phases = [r for r in results if 'waxing' in r['phase']]
        waning_phases = [r for r in results if 'waning' in r['phase']]

        if waxing_phases and waning_phases:
            waxing_avg = sum(p['avg_sentiment'] for p in waxing_phases) / len(waxing_phases)
            waning_avg = sum(p['avg_sentiment'] for p in waning_phases) / len(waning_phases)

            if waxing_avg - waning_avg > 0.15:
                insights.append(
                    f"📈 Your mood tends to brighten as the moon waxes (grows fuller)"
                )
            elif waning_avg - waxing_avg > 0.15:
                insights.append(
                    f"📉 You seem more reflective and introspective as the moon wanes"
                )

    return {
        'phases': results,
        'insights': insights,
        'period_days': days,
        'total_entries': sum(r['count'] for r in results),
    }


def generate_weather_correlation(user: User, days: int = 90) -> Dict:
    """
    Correlate mood with weather conditions over the specified period.

    Returns aggregated sentiment and mood counts by weather condition.
    """
    from apps.journal.models import Entry
    from datetime import timedelta
    from django.utils import timezone

    start_date = timezone.now().date() - timedelta(days=days)

    # Get entries with weather data
    entries = Entry.objects.filter(
        user=user,
        entry_date__gte=start_date,
        is_analyzed=True
    ).select_related('analysis').exclude(
        analysis__weather_condition=''
    )

    # Aggregate by weather condition
    weather_data = defaultdict(lambda: {
        'count': 0,
        'total_sentiment': 0.0,
        'total_temp': 0.0,
        'moods': defaultdict(int),
    })

    for entry in entries:
        if not hasattr(entry, 'analysis'):
            continue

        condition = entry.analysis.weather_condition
        if not condition:
            continue

        weather_data[condition]['count'] += 1
        weather_data[condition]['total_sentiment'] += entry.analysis.sentiment_score
        if entry.analysis.temperature:
            weather_data[condition]['total_temp'] += entry.analysis.temperature
        weather_data[condition]['moods'][entry.analysis.detected_mood] += 1

    # Calculate averages and format results
    results = []
    for condition, data in weather_data.items():
        if data['count'] == 0:
            continue

        avg_sentiment = data['total_sentiment'] / data['count']
        avg_temp = data['total_temp'] / data['count'] if data['total_temp'] else None
        dominant_mood = max(data['moods'].items(), key=lambda x: x[1])[0] if data['moods'] else ''

        results.append({
            'condition': condition,
            'display_name': WEATHER_DISPLAY.get(condition, condition.title()),
            'icon': get_weather_icon(condition),
            'count': data['count'],
            'avg_sentiment': round(avg_sentiment, 3),
            'avg_temperature': round(avg_temp, 1) if avg_temp else None,
            'sentiment_label': 'positive' if avg_sentiment > 0.05 else ('negative' if avg_sentiment < -0.05 else 'neutral'),
            'dominant_mood': dominant_mood,
        })

    # Sort by count (most common first)
    results.sort(key=lambda x: x['count'], reverse=True)

    # Generate insights
    insights = []
    if results:
        # Find most positive weather
        most_positive = max(results, key=lambda x: x['avg_sentiment'])
        if most_positive['avg_sentiment'] > 0.1:
            insights.append(
                f"You tend to be happiest on {most_positive['display_name'].lower()} days"
            )

        # Check if rainy days are notably different
        rain_data = next((r for r in results if r['condition'] in ['rain', 'drizzle']), None)
        clear_data = next((r for r in results if r['condition'] == 'clear'), None)

        if rain_data and clear_data:
            diff = clear_data['avg_sentiment'] - rain_data['avg_sentiment']
            if diff > 0.15:
                insights.append(
                    "Sunny days seem to boost your mood compared to rainy ones"
                )
            elif diff < -0.1:
                insights.append(
                    "Interestingly, rainy days don't seem to dampen your spirits!"
                )

    return {
        'conditions': results,
        'insights': insights,
        'period_days': days,
        'total_entries': sum(r['count'] for r in results),
    }


def generate_zodiac_insights(user: User) -> Optional[Dict]:
    """
    Generate zodiac-based patterns for the user.

    Only returns data if user has horoscope enabled.
    """
    from apps.journal.models import Entry
    from django.utils import timezone

    profile = user.profile
    if not profile.horoscope_enabled or not profile.birthday:
        return None

    zodiac_sign = profile.zodiac_sign
    if not zodiac_sign:
        return None

    # Get all analyzed entries for this user
    entries = Entry.objects.filter(
        user=user,
        is_analyzed=True
    ).select_related('analysis')

    if not entries.exists():
        return None

    # Calculate overall stats
    sentiments = [e.analysis.sentiment_score for e in entries if hasattr(e, 'analysis')]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

    # Get mood distribution
    moods = defaultdict(int)
    for entry in entries:
        if hasattr(entry, 'analysis'):
            moods[entry.analysis.detected_mood] += 1

    dominant_mood = max(moods.items(), key=lambda x: x[1])[0] if moods else ''

    element = get_zodiac_element(zodiac_sign)

    # Generate element-specific insights
    element_insights = {
        'fire': "As a fire sign, you tend to write with passion and energy",
        'earth': "As an earth sign, your entries often show practical wisdom",
        'air': "As an air sign, your writing often explores ideas and connections",
        'water': "As a water sign, your entries tend to be deeply emotional and intuitive",
    }

    insights = []
    if element in element_insights:
        insights.append(element_insights[element])

    if avg_sentiment > 0.15:
        insights.append("Your overall journaling sentiment is quite positive")
    elif avg_sentiment < -0.1:
        insights.append("Your journal reflects some challenging experiences")

    return {
        'sign': zodiac_sign,
        'display_name': ZODIAC_DISPLAY.get(zodiac_sign, zodiac_sign.title()),
        'symbol': ZODIAC_SYMBOLS.get(zodiac_sign, ''),
        'element': element,
        'element_color': ELEMENT_COLORS.get(element, '#6b7280'),
        'avg_sentiment': round(avg_sentiment, 3),
        'dominant_mood': dominant_mood,
        'total_entries': len(entries),
        'insights': insights,
    }


def get_weather_icon(condition: str) -> str:
    """Get Bootstrap icon class for a weather condition."""
    icons = {
        'clear': 'bi-sun',
        'clouds': 'bi-cloud',
        'rain': 'bi-cloud-rain',
        'drizzle': 'bi-cloud-drizzle',
        'thunderstorm': 'bi-cloud-lightning-rain',
        'snow': 'bi-cloud-snow',
        'mist': 'bi-cloud-haze',
        'fog': 'bi-cloud-fog',
        'haze': 'bi-cloud-haze',
    }
    return icons.get(condition.lower(), 'bi-cloud')


def generate_all_correlations(user: User, days: int = 90) -> Dict:
    """
    Generate all correlation insights for a user.

    Convenience function to get moon, weather, and zodiac insights at once.
    """
    return {
        'moon': generate_moon_correlation(user, days),
        'weather': generate_weather_correlation(user, days),
        'zodiac': generate_zodiac_insights(user),
    }
