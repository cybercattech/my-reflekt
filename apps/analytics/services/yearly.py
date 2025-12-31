"""
Yearly review generation service.

Generates comprehensive year-in-review data from analyzed entries.
"""
from collections import Counter
from django.contrib.auth import get_user_model

User = get_user_model()


def generate_yearly_review_sync(user_id: int, year: int) -> str:
    """
    Generate full year-in-review for a user (synchronous version).

    Called from views when regenerating reviews.
    """
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
            'sentiment': float(s.avg_sentiment) if s.avg_sentiment else 0,
            'mood': s.dominant_mood,
            'entries': s.entry_count,
        }
        for s in monthly_snapshots
    ]

    # Theme analysis
    all_themes = []
    for e in entries:
        if hasattr(e, 'analysis'):
            all_themes.extend(e.analysis.themes or [])
    theme_counts = Counter(all_themes)
    top_themes = [theme for theme, _ in theme_counts.most_common(10)]

    # Theme sentiments and entry counts for top 5 themes
    theme_sentiments = {}
    theme_entry_counts = {}
    for theme in top_themes[:5]:
        theme_entries = [
            e for e in entries
            if hasattr(e, 'analysis') and theme in (e.analysis.themes or [])
        ]
        if theme_entries:
            theme_sentiments[theme] = sum(
                e.analysis.sentiment_score for e in theme_entries
            ) / len(theme_entries)
            theme_entry_counts[theme] = len(theme_entries)

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
            'preview': e.content[:100] + '...' if len(e.content) > 100 else e.content,
        }
        for e in sorted_by_sentiment[:10]
    ]

    lowlights = [
        {
            'id': e.id,
            'date': e.entry_date.isoformat(),
            'sentiment': e.analysis.sentiment_score,
            'mood': e.analysis.detected_mood,
            'preview': e.content[:100] + '...' if len(e.content) > 100 else e.content,
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
    review, created = YearlyReview.objects.update_or_create(
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
            'theme_entry_counts': theme_entry_counts,
            'highlights': highlights,
            'lowlights': lowlights,
            'insights': insights,
        }
    )

    return f"Generated yearly review for {user.email} {year}"
