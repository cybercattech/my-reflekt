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

        # Get mood distribution
        moods = data['moods']
        dominant_mood = max(moods.items(), key=lambda x: x[1])[0] if moods else ''

        # Calculate sentiment-aligned mood display based on actual sentiment score
        positive_moods = moods.get('ecstatic', 0) + moods.get('happy', 0)
        negative_moods = moods.get('sad', 0) + moods.get('angry', 0)
        total = data['count']

        # Determine display mood based on sentiment score (not dominant mood count)
        # This ensures the label matches what the sentiment actually indicates
        if total > 0:
            pos_pct = positive_moods / total
            neg_pct = negative_moods / total

            # Check for mixed moods (both positive and negative present significantly)
            has_mixed_moods = pos_pct > 0.25 and neg_pct > 0.25

            if avg_sentiment >= 0.6:
                display_mood = 'ecstatic'
            elif avg_sentiment >= 0.4:
                display_mood = 'happy'
            elif avg_sentiment >= 0.2:
                display_mood = 'upbeat'
            elif avg_sentiment >= -0.2:
                # Neutral range - check if it's mixed or truly neutral
                if has_mixed_moods:
                    display_mood = 'mixed'
                else:
                    display_mood = 'neutral'
            elif avg_sentiment >= -0.4:
                display_mood = 'reflective'
            elif avg_sentiment >= -0.6:
                display_mood = 'sad'
            else:
                display_mood = 'difficult'
        else:
            display_mood = dominant_mood

        results.append({
            'phase': phase,
            'display_name': MOON_PHASE_DISPLAY.get(phase, phase.replace('_', ' ').title()),
            'icon': MOON_PHASE_ICONS.get(phase, 'bi-moon'),
            'count': data['count'],
            'avg_sentiment': round(avg_sentiment, 3),
            'sentiment_label': 'positive' if avg_sentiment > 0.05 else ('negative' if avg_sentiment < -0.05 else 'neutral'),
            'dominant_mood': dominant_mood,
            'display_mood': display_mood,
        })

    # Sort by average sentiment
    results.sort(key=lambda x: x['avg_sentiment'], reverse=True)

    # Generate insights based on display_mood (sentiment-aligned)
    insights = []

    if results:
        best_phase = results[0]
        worst_phase = results[-1]

        # Full moon specific insights
        full_moon_data = next((r for r in results if r['phase'] == 'full_moon'), None)
        if full_moon_data and full_moon_data['count'] >= 2:
            mood = full_moon_data['display_mood']
            sentiment = full_moon_data['avg_sentiment']
            if sentiment >= 0.4:
                insights.append(f"🌕 Full moons bring out your brightest, most {mood} writing")
            elif sentiment >= 0.2:
                insights.append(f"🌕 Your full moon entries tend to be {mood} and positive")
            elif sentiment >= -0.2:
                if mood == 'mixed':
                    insights.append(f"🌕 Full moon brings varied emotions - a mix of highs and lows")
                else:
                    insights.append(f"🌕 Your full moon writing is generally balanced and {mood}")
            else:
                insights.append(f"🌕 Full moon phases tend to bring more reflective, introspective writing")

        # New moon insights
        new_moon_data = next((r for r in results if r['phase'] == 'new_moon'), None)
        if new_moon_data and new_moon_data['count'] >= 2:
            mood = new_moon_data['display_mood']
            sentiment = new_moon_data['avg_sentiment']
            if sentiment >= 0.4:
                insights.append(f"🌑 New moons inspire {mood} energy in your entries")
            elif sentiment >= 0.2:
                insights.append(f"🌑 Your new moon writing tends to be {mood}")
            elif sentiment >= -0.2:
                if mood == 'mixed':
                    insights.append(f"🌑 New moon brings emotional variety - both light and shadow")
                else:
                    insights.append(f"🌑 New moon writing is balanced, with {mood} undertones")
            else:
                insights.append(f"🌑 New moon phases bring more contemplative, introspective moods")

        # General best phase (if not already covered)
        if best_phase['avg_sentiment'] >= 0.3 and best_phase['phase'] not in ['full_moon', 'new_moon']:
            insights.append(
                f"✨ You feel most {best_phase['display_mood']} during {best_phase['display_name']} phases"
            )

        # Worst phase (if significantly different)
        if worst_phase['avg_sentiment'] < -0.1 and best_phase != worst_phase:
            sentiment_diff = best_phase['avg_sentiment'] - worst_phase['avg_sentiment']
            if sentiment_diff > 0.3:
                insights.append(
                    f"🌙 {worst_phase['display_name']} phases tend toward more {worst_phase['display_mood']} moods"
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

    Returns aggregated sentiment by temperature range and weather condition.
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
    ).exclude(
        analysis__temperature__isnull=True
    )

    # Define temperature ranges (in Fahrenheit)
    temp_ranges = [
        ('cold', 0, 30, '<30°'),
        ('cool', 30, 60, '30-59°'),
        ('mild', 60, 80, '60-79°'),
        ('warm', 80, 100, '80-99°'),
        ('hot', 100, 200, '≥100°'),
    ]

    # Aggregate by temperature range and weather condition
    weather_temp_data = defaultdict(lambda: {
        'count': 0,
        'total_sentiment': 0.0,
        'moods': defaultdict(int),
        'conditions': defaultdict(int),
    })

    for entry in entries:
        if not hasattr(entry, 'analysis'):
            continue

        condition = entry.analysis.weather_condition
        temp_celsius = entry.analysis.temperature

        if not condition or temp_celsius is None:
            continue

        # Convert Celsius to Fahrenheit
        temp = (temp_celsius * 9/5) + 32

        # Determine temperature range
        temp_range_key = None
        for key, min_temp, max_temp, label in temp_ranges:
            if min_temp <= temp < max_temp:
                temp_range_key = key
                break

        if not temp_range_key:
            continue

        weather_temp_data[temp_range_key]['count'] += 1
        weather_temp_data[temp_range_key]['total_sentiment'] += entry.analysis.sentiment_score
        weather_temp_data[temp_range_key]['moods'][entry.analysis.detected_mood] += 1
        weather_temp_data[temp_range_key]['conditions'][condition] += 1

    # Format results by temperature range
    temp_range_results = []
    for range_key, min_temp, max_temp, label in temp_ranges:
        if range_key not in weather_temp_data:
            continue

        data = weather_temp_data[range_key]
        if data['count'] == 0:
            continue

        avg_sentiment = data['total_sentiment'] / data['count']
        dominant_mood = max(data['moods'].items(), key=lambda x: x[1])[0] if data['moods'] else ''

        # Get ALL conditions for this temperature range (sorted by frequency)
        condition_breakdown = []
        sorted_conditions = sorted(data['conditions'].items(), key=lambda x: x[1], reverse=True)
        for condition, count in sorted_conditions:
            condition_breakdown.append({
                'condition': condition,
                'display_name': WEATHER_DISPLAY.get(condition, condition.title()),
                'icon': get_weather_icon(condition),
                'count': count,
            })

        temp_range_results.append({
            'range_key': range_key,
            'range_label': label,
            'min_temp': min_temp,
            'max_temp': max_temp,
            'count': data['count'],
            'avg_sentiment': round(avg_sentiment, 3),
            'sentiment_label': 'positive' if avg_sentiment > 0.05 else ('negative' if avg_sentiment < -0.05 else 'neutral'),
            'dominant_mood': dominant_mood,
            'conditions': condition_breakdown,
        })

    # Sort by temperature range (coldest to hottest)
    temp_range_results.sort(key=lambda x: x['min_temp'])

    # Generate insights
    insights = []
    if temp_range_results:
        # Find temperature range with best mood
        best_range = max(temp_range_results, key=lambda x: x['avg_sentiment'])
        if best_range['avg_sentiment'] > 0.1:
            insights.append(
                f"You're happiest in {best_range['range_label'].lower()} weather"
            )

        # Check for temperature extremes
        if len(temp_range_results) >= 3:
            coldest = min(temp_range_results, key=lambda x: x['min_temp'])
            warmest = max(temp_range_results, key=lambda x: x['max_temp'])

            if abs(coldest['avg_sentiment'] - warmest['avg_sentiment']) > 0.2:
                if coldest['avg_sentiment'] > warmest['avg_sentiment']:
                    insights.append("Cold weather seems to suit you better than heat")
                else:
                    insights.append("Warm weather tends to improve your mood")

    return {
        'temp_ranges': temp_range_results,
        'insights': insights,
        'period_days': days,
        'total_entries': sum(r['count'] for r in temp_range_results),
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
