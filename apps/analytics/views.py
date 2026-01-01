"""
Dashboard views for analytics and insights.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta

from apps.accounts.decorators import premium_required
from .models import MonthlySnapshot, YearlyReview
from .tasks import generate_yearly_review


@login_required
def dashboard(request):
    """Main dashboard with current insights."""
    import json
    from collections import defaultdict
    from apps.journal.models import Entry, EntryCapture
    from .models import TrackedBook, TrackedPerson, EntryAnalysis
    from django.db.models import Sum, Avg, Count, F

    user = request.user
    now = timezone.now()
    current_year = now.year

    # Ensure user has a profile (safety check for edge cases)
    from apps.accounts.models import Profile
    try:
        _ = user.profile
    except Profile.DoesNotExist:
        Profile.objects.create(user=user)

    # Get current month snapshot
    current_snapshot = MonthlySnapshot.objects.filter(
        user=user,
        year=now.year,
        month=now.month
    ).first()

    # Get last 6 months for trend - serialize for JavaScript
    snapshots_qs = MonthlySnapshot.objects.filter(
        user=user
    ).order_by('-year', '-month')[:6]

    snapshots_data = [
        {
            'month_name': s.month_name,
            'year': s.year,
            'avg_sentiment': float(s.avg_sentiment) if s.avg_sentiment else 0,
            'entry_count': s.entry_count
        }
        for s in reversed(list(snapshots_qs))
    ]

    # Serialize mood distribution for JavaScript
    mood_distribution_json = json.dumps(
        current_snapshot.mood_distribution if current_snapshot else {}
    )

    # Get recent entries
    recent_entries = Entry.objects.filter(
        user=user
    ).select_related('analysis')[:5]

    # Calculate overall stats
    stats = Entry.objects.filter(user=user).aggregate(
        total_entries=Count('id'),
        total_words=Sum('word_count'),
    )

    # Monthly entry counts for insight cards
    monthly_entry_counts = []
    monthly_entry_counts_prev_year = []
    monthly_entry_counts_all_time = []
    prev_year = current_year - 1

    for month_num in range(1, 13):
        # Current year
        count_current = Entry.objects.filter(
            user=user,
            entry_date__year=current_year,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts.append(count_current)

        # Previous year
        count_prev = Entry.objects.filter(
            user=user,
            entry_date__year=prev_year,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts_prev_year.append(count_prev)

        # All time
        count_all = Entry.objects.filter(
            user=user,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts_all_time.append(count_all)

    entries_this_year = sum(monthly_entry_counts)
    entries_prev_year = sum(monthly_entry_counts_prev_year)

    # Journaled days count
    journaled_days = Entry.objects.filter(user=user).values('entry_date').distinct().count()
    stats['journaled_days'] = journaled_days
    stats['entries_this_year'] = entries_this_year
    stats['entries_prev_year'] = entries_prev_year

    # Perfect months - months where user wrote every single day
    import calendar
    from collections import defaultdict

    # Get all entry dates grouped by year-month
    all_entry_dates = Entry.objects.filter(user=user).values_list('entry_date', flat=True)
    entries_by_month = defaultdict(set)
    for entry_date in all_entry_dates:
        key = (entry_date.year, entry_date.month)
        entries_by_month[key].add(entry_date.day)

    # Count perfect months
    perfect_months = 0
    for (year, month), days in entries_by_month.items():
        days_in_month = calendar.monthrange(year, month)[1]
        if len(days) == days_in_month:
            perfect_months += 1

    stats['perfect_months'] = perfect_months

    # =========================================================================
    # Capture summaries for dashboard cards
    # =========================================================================

    # Currently reading books
    books_reading = TrackedBook.objects.filter(
        user=user, status='reading'
    )[:3]
    books_finished_year = TrackedBook.objects.filter(
        user=user, status='finished', finished_date__year=current_year
    ).count()

    # Top people (most mentioned)
    top_people = TrackedPerson.objects.filter(user=user)[:5]

    # Recent media watched this year
    recent_watched = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='watched',
        entry__entry_date__year=current_year
    ).select_related('entry').order_by('-entry__entry_date')[:5]
    watched_count_year = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='watched',
        entry__entry_date__year=current_year
    ).count()

    # Workout count this year
    workout_count_year = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='workout',
        entry__entry_date__year=current_year
    ).count()

    # Travel entries (look for location captures or travel theme)
    travel_entries = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='location',
        entry__entry_date__year=current_year
    ).select_related('entry').order_by('-entry__entry_date')[:5]

    # =========================================================================
    # Mood-Theme Insights: "You're happiest when..."
    # =========================================================================
    insights = []

    # Get all analyzed entries with positive sentiment
    positive_analyses = EntryAnalysis.objects.filter(
        entry__user=user,
        sentiment_label='positive'
    ).select_related('entry')

    negative_analyses = EntryAnalysis.objects.filter(
        entry__user=user,
        sentiment_label='negative'
    ).select_related('entry')

    # Count themes for positive vs negative entries
    positive_themes = defaultdict(int)
    negative_themes = defaultdict(int)
    positive_keywords = defaultdict(int)

    for analysis in positive_analyses:
        for theme in (analysis.themes or []):
            positive_themes[theme] += 1
        for keyword in (analysis.keywords or [])[:5]:  # Top 5 keywords per entry
            positive_keywords[keyword.lower()] += 1

    for analysis in negative_analyses:
        for theme in (analysis.themes or []):
            negative_themes[theme] += 1

    # Find themes that correlate most with happiness
    if positive_themes:
        best_theme = max(positive_themes, key=positive_themes.get)
        if positive_themes[best_theme] >= 2:  # At least 2 occurrences
            insights.append({
                'type': 'happy_theme',
                'icon': 'bi-emoji-smile',
                'color': 'success',
                'text': f"You're happiest when writing about <strong>{best_theme}</strong>",
                'detail': f"{positive_themes[best_theme]} positive entries"
            })

    # Find what keywords appear most in positive entries
    if positive_keywords:
        top_happy_keywords = sorted(
            positive_keywords.items(), key=lambda x: x[1], reverse=True
        )[:3]
        if top_happy_keywords and top_happy_keywords[0][1] >= 2:
            keywords_str = ', '.join([k[0] for k in top_happy_keywords])
            insights.append({
                'type': 'happy_keywords',
                'icon': 'bi-key',
                'color': 'primary',
                'text': f"Words in your happiest entries: <strong>{keywords_str}</strong>",
                'detail': ''
            })

    # Person correlation - who makes you happy?
    person_sentiment = defaultdict(lambda: {'positive': 0, 'negative': 0, 'total': 0})
    person_entries = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='person'
    ).select_related('entry__analysis')

    for capture in person_entries:
        person_name = capture.data.get('name', 'Unknown')
        if hasattr(capture.entry, 'analysis') and capture.entry.analysis:
            label = capture.entry.analysis.sentiment_label
            person_sentiment[person_name][label] += 1
            person_sentiment[person_name]['total'] += 1

    # Find person most correlated with happiness
    happy_person = None
    happy_person_score = 0
    for person, scores in person_sentiment.items():
        if scores['total'] >= 2:  # At least 2 mentions
            positivity = scores['positive'] / scores['total']
            if positivity > happy_person_score:
                happy_person = person
                happy_person_score = positivity

    if happy_person and happy_person_score >= 0.6:  # 60%+ positive
        insights.append({
            'type': 'happy_person',
            'icon': 'bi-person-heart',
            'color': 'danger',
            'text': f"You tend to be happier when mentioning <strong>{happy_person}</strong>",
            'detail': f"{int(happy_person_score * 100)}% positive entries"
        })

    # Writing streak / consistency insight
    from datetime import timedelta
    recent_dates = Entry.objects.filter(
        user=user,
        entry_date__gte=now.date() - timedelta(days=30)
    ).values_list('entry_date', flat=True).distinct()

    if len(recent_dates) >= 7:
        insights.append({
            'type': 'streak',
            'icon': 'bi-fire',
            'color': 'warning',
            'text': f"Great consistency! You've written <strong>{len(recent_dates)} days</strong> in the last month",
            'detail': ''
        })

    # ==========================================================================
    # Environmental Correlations (Moon, Weather, Zodiac)
    # ==========================================================================
    from apps.analytics.services.insights import generate_all_correlations
    correlations = generate_all_correlations(user, days=180)

    # ==========================================================================
    # Daily Devotion (if enabled)
    # ==========================================================================
    daily_devotion = None
    if user.profile.devotion_enabled:
        from apps.analytics.services.devotion import get_daily_devotion
        daily_devotion = get_daily_devotion()

    # ==========================================================================
    # Streak Badges
    # ==========================================================================
    from apps.accounts.models import UserBadge
    from datetime import timedelta

    # Calculate actual current streak from entry dates
    all_entry_dates = set(
        Entry.objects.filter(user=user).values_list('entry_date', flat=True)
    )
    current_streak = 0
    check_date = now.date()
    # If no entry today, start from yesterday
    if check_date not in all_entry_dates:
        check_date = now.date() - timedelta(days=1)
    while check_date in all_entry_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    earned_badges = UserBadge.get_user_badges(user)
    next_badge = UserBadge.get_next_badge(user, current_streak)

    return render(request, 'dashboard/index.html', {
        'current_snapshot': current_snapshot,
        'snapshots_json': json.dumps(snapshots_data),
        'mood_distribution_json': mood_distribution_json,
        'recent_entries': recent_entries,
        'stats': stats,
        'current_year': now.year,
        'current_month': now.month,
        # Monthly entry data for insight cards chart
        'monthly_entry_counts': monthly_entry_counts,
        'monthly_entry_counts_prev_year': monthly_entry_counts_prev_year,
        'monthly_entry_counts_all_time': monthly_entry_counts_all_time,
        # Capture summaries
        'books_reading': books_reading,
        'books_finished_year': books_finished_year,
        'top_people': top_people,
        'recent_watched': recent_watched,
        'watched_count_year': watched_count_year,
        'workout_count_year': workout_count_year,
        'travel_entries': travel_entries,
        # Insights
        'insights': insights,
        # Environmental correlations
        'correlations': correlations,
        'moon_correlation': correlations.get('moon'),
        'weather_correlation': correlations.get('weather'),
        'zodiac_insights': correlations.get('zodiac'),
        # Daily devotion
        'daily_devotion': daily_devotion,
        # Streak badges
        'earned_badges': earned_badges,
        'next_badge': next_badge,
        'current_streak': current_streak,
        # Sidebar
        'active_page': 'dashboard',
    })


@login_required
@premium_required
def monthly_view(request, year, month):
    """Detailed view for a specific month."""
    user = request.user

    # Get snapshot if it exists (may not exist for new users or months with no entries)
    snapshot = MonthlySnapshot.objects.filter(
        user=user,
        year=year,
        month=month
    ).first()

    # Create empty snapshot-like object if none exists
    if not snapshot:
        snapshot = type('EmptySnapshot', (), {
            'entry_count': 0,
            'total_words': 0,
            'avg_sentiment': 0.0,
            'dominant_mood': 'neutral',
            'mood_distribution': {},
            'top_themes': [],
        })()

    # Get all entries for this month
    from apps.journal.models import Entry
    entries = Entry.objects.filter(
        user=user,
        entry_date__year=year,
        entry_date__month=month
    ).select_related('analysis').order_by('entry_date')

    # Get all years where user has entries for year selector
    available_years = Entry.objects.filter(user=user).dates(
        'entry_date', 'year', order='DESC'
    )
    available_years = [d.year for d in available_years]

    # Build calendar data
    import calendar
    cal = calendar.Calendar()
    month_days = list(cal.itermonthdays(year, month))

    # Map entries to days
    entry_map = {e.entry_date.day: e for e in entries}

    # Calculate average sentiment per day of week (0=Monday, 6=Sunday)
    from collections import defaultdict
    weekday_sentiments = defaultdict(list)
    for entry in entries:
        if hasattr(entry, 'analysis') and entry.analysis:
            # Python weekday: 0=Monday, but we want 0=Sunday for display
            weekday = (entry.entry_date.weekday() + 1) % 7  # Convert to 0=Sunday
            weekday_sentiments[weekday].append(entry.analysis.sentiment_score)

    # Calculate averages for each day of week
    weekday_averages = {}
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    weekday_list = []
    for day in range(7):  # 0=Sun, 1=Mon, ..., 6=Sat
        if weekday_sentiments[day]:
            avg = sum(weekday_sentiments[day]) / len(weekday_sentiments[day])
            weekday_averages[day] = round(avg, 2)
        else:
            weekday_averages[day] = None
        weekday_list.append({
            'name': day_names[day],
            'avg': weekday_averages[day]
        })

    return render(request, 'dashboard/monthly.html', {
        'snapshot': snapshot,
        'entries': entries,
        'entry_map': entry_map,
        'month_days': month_days,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'current_year': year,
        'available_years': available_years,
        'weekday_averages': weekday_averages,
        'weekday_list': weekday_list,
        'active_page': 'monthly',
    })


@login_required
def yearly_view(request, year):
    """Year-in-review page."""
    import json
    from apps.journal.models import Entry
    user = request.user

    # Check if user is premium
    is_premium = user.profile.is_premium

    # Get all years where user has entries
    available_years = Entry.objects.filter(user=user).dates(
        'entry_date', 'year', order='DESC'
    )
    available_years = [d.year for d in available_years]

    review = None
    monthly_snapshots = []
    monthly_trend_json = '[]'

    # Only generate/fetch data for premium users
    if is_premium:
        # Try to get existing review
        review = YearlyReview.objects.filter(user=user, year=year).first()

        # If no review exists, generate it
        if not review:
            # Check if there are entries for this year
            from apps.journal.models import Entry
            entry_count = Entry.objects.filter(
                user=user,
                entry_date__year=year,
                is_analyzed=True
            ).count()

            if entry_count > 0:
                # Generate synchronously for now (could be async with loading state)
                generate_yearly_review(user.id, year)
                review = YearlyReview.objects.filter(user=user, year=year).first()

        # Get monthly snapshots for chart
        monthly_snapshots = MonthlySnapshot.objects.filter(
            user=user,
            year=year
        ).order_by('month')

        # Serialize monthly_trend for JavaScript
        monthly_trend_json = json.dumps(review.monthly_trend) if review and review.monthly_trend else '[]'

    # Prepare theme data for radar chart (top 5 themes with entry counts)
    theme_radar_json = '[]'
    if review and review.top_themes:
        theme_entry_counts = review.theme_entry_counts or {}
        theme_sentiments = review.theme_sentiments or {}
        theme_radar_data = []
        for theme in review.top_themes[:5]:
            theme_radar_data.append({
                'theme': theme,
                'count': theme_entry_counts.get(theme, 0),
                'sentiment': theme_sentiments.get(theme, 0),
            })
        theme_radar_json = json.dumps(theme_radar_data)

    return render(request, 'dashboard/yearly.html', {
        'review': review,
        'monthly_snapshots': monthly_snapshots,
        'monthly_trend_json': monthly_trend_json,
        'theme_radar_json': theme_radar_json,
        'year': year,
        'current_year': year,
        'available_years': available_years,
        'active_page': 'yearly',
        'is_premium': is_premium,
    })


@login_required
@premium_required
def regenerate_yearly(request, year):
    """Force regenerate yearly review."""
    if request.method == 'POST':
        # Call synchronously instead of using Celery
        try:
            from apps.analytics.services.yearly import generate_yearly_review_sync
            generate_yearly_review_sync(request.user.id, year)
            from django.contrib import messages
            messages.success(request, f'{year} review regenerated successfully!')
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error regenerating review: {str(e)}')

    from django.shortcuts import redirect
    return redirect('analytics:yearly', year=year)


# =============================================================================
# Capture Analytics Views
# =============================================================================

@login_required
def captures_dashboard(request):
    """Main captures dashboard with overview of all tracked items."""
    from apps.journal.models import EntryCapture
    from .models import TrackedBook, TrackedPerson, CaptureSnapshot
    from django.db.models import Sum, Count

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    # Check if user is premium
    is_premium = user.profile.is_premium

    if is_premium:
        # Books summary
        books_reading = TrackedBook.objects.filter(user=user, status='reading')
        books_finished_year = TrackedBook.objects.filter(
            user=user,
            status='finished',
            finished_date__year=year
        )

        # Media summary (query-based)
        watched_year = EntryCapture.objects.filter(
            entry__user=user,
            capture_type='watched',
            entry__entry_date__year=year
        ).count()

        # People summary
        top_people = TrackedPerson.objects.filter(user=user)[:5]

        # Workout summary
        workout_captures = EntryCapture.objects.filter(
            entry__user=user,
            capture_type='workout',
            entry__entry_date__year=year
        )
        workout_count = workout_captures.count()
        total_workout_duration = sum(
            c.data.get('duration', 0) for c in workout_captures
            if isinstance(c.data.get('duration'), (int, float))
        )

        # Get available years for dropdown
        years_with_data = EntryCapture.objects.filter(
            entry__user=user
        ).dates('entry__entry_date', 'year').values_list('entry__entry_date__year', flat=True)
        available_years = sorted(set(years_with_data), reverse=True) if years_with_data else [now.year]

        books_reading_count = books_reading.count()
        books_finished_count = books_finished_year.count()
        people_count = TrackedPerson.objects.filter(user=user).count()
    else:
        # Free user - return empty data
        books_reading = []
        books_reading_count = 0
        books_finished_count = 0
        watched_year = 0
        top_people = []
        people_count = 0
        workout_count = 0
        total_workout_duration = 0
        available_years = [now.year]

    return render(request, 'dashboard/captures/index.html', {
        'year': year,
        'available_years': available_years,
        'books_reading': books_reading,
        'books_reading_count': books_reading_count,
        'books_finished_count': books_finished_count,
        'watched_count': watched_year,
        'top_people': top_people,
        'people_count': people_count,
        'workout_count': workout_count,
        'total_workout_duration': total_workout_duration,
        'current_year': year,
        'active_page': 'captures',
        'is_premium': is_premium,
    })


@login_required
@premium_required
def books_dashboard(request):
    """Detailed books analytics."""
    from .models import TrackedBook
    from django.db.models import Count, Avg
    from django.db.models.functions import TruncMonth

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    currently_reading = TrackedBook.objects.filter(user=user, status='reading')
    want_to_read = TrackedBook.objects.filter(user=user, status='want_to_read')

    finished_this_year = TrackedBook.objects.filter(
        user=user,
        status='finished',
        finished_date__year=year
    ).order_by('-finished_date')

    all_finished = TrackedBook.objects.filter(
        user=user,
        status='finished'
    ).order_by('-finished_date')

    # Books by month for chart (this year)
    monthly_counts = [0] * 12
    for book in finished_this_year:
        if book.finished_date:
            monthly_counts[book.finished_date.month - 1] += 1

    # Reading stats
    rated_books = all_finished.filter(rating__isnull=False)
    avg_rating = rated_books.aggregate(Avg('rating'))['rating__avg']

    stats = {
        'total_finished': finished_this_year.count(),
        'total_all_time': all_finished.count(),
        'avg_rating': round(avg_rating, 1) if avg_rating else None,
        'currently_reading': currently_reading.count(),
        'want_to_read': want_to_read.count(),
    }

    # Get available years
    years_with_books = TrackedBook.objects.filter(
        user=user,
        finished_date__isnull=False
    ).dates('finished_date', 'year').values_list('finished_date__year', flat=True)
    available_years = sorted(set(years_with_books), reverse=True) if years_with_books else [now.year]

    return render(request, 'dashboard/captures/books.html', {
        'year': year,
        'available_years': available_years,
        'currently_reading': currently_reading,
        'want_to_read': want_to_read,
        'finished_books': finished_this_year,
        'monthly_counts': monthly_counts,
        'stats': stats,
        'current_year': year,
        'active_page': 'books',
    })


@login_required
@premium_required
def media_dashboard(request):
    """Movies and shows watched analytics."""
    from apps.journal.models import EntryCapture

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    watched = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='watched',
        entry__entry_date__year=year
    ).select_related('entry').order_by('-entry__entry_date')

    # Stats by rating and type
    by_rating = {}
    by_type = {}
    monthly_counts = [0] * 12

    for item in watched:
        rating = item.data.get('rating')
        if rating:
            by_rating[rating] = by_rating.get(rating, 0) + 1
        mtype = item.data.get('type', 'movie')
        by_type[mtype] = by_type.get(mtype, 0) + 1
        # Monthly
        monthly_counts[item.entry.entry_date.month - 1] += 1

    # Get available years
    years_with_media = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='watched'
    ).dates('entry__entry_date', 'year').values_list('entry__entry_date__year', flat=True)
    available_years = sorted(set(years_with_media), reverse=True) if years_with_media else [now.year]

    return render(request, 'dashboard/captures/media.html', {
        'year': year,
        'available_years': available_years,
        'watched': watched,
        'by_rating': by_rating,
        'by_type': by_type,
        'monthly_counts': monthly_counts,
        'total': watched.count(),
        'current_year': year,
        'active_page': 'media',
    })


@login_required
@premium_required
def people_dashboard(request):
    """Social connections analytics."""
    from apps.journal.models import EntryCapture
    from .models import TrackedPerson
    from django.db.models.functions import TruncMonth
    from django.db.models import Count
    import json

    user = request.user

    people = TrackedPerson.objects.filter(user=user).order_by('-mention_count')

    # Monthly mentions for heatmap
    monthly_mentions_qs = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='person'
    ).annotate(
        month=TruncMonth('entry__entry_date')
    ).values('month').annotate(count=Count('id')).order_by('month')

    # Convert to list and then JSON-serializable format (datetime -> string)
    monthly_mentions_list = list(monthly_mentions_qs)
    monthly_mentions_json = json.dumps([
        {'month': item['month'].isoformat(), 'count': item['count']}
        for item in monthly_mentions_list
    ])

    # By relationship
    by_relationship = {}
    for person in people:
        rel = person.get_relationship_display()
        by_relationship[rel] = by_relationship.get(rel, 0) + 1

    # Convert to JSON for JavaScript
    by_relationship_json = json.dumps(by_relationship)

    now = timezone.now()
    return render(request, 'dashboard/captures/people.html', {
        'people': people,
        'monthly_mentions': monthly_mentions_json,
        'has_monthly_mentions': bool(monthly_mentions_list),
        'by_relationship': by_relationship_json,
        'has_relationship_data': bool(by_relationship),
        'total_people': people.count(),
        'total_mentions': sum(p.mention_count for p in people),
        'current_year': now.year,
        'active_page': 'people',
    })


@login_required
@premium_required
def person_detail(request, pk):
    """Get person details for edit modal."""
    from .models import TrackedPerson
    import json

    try:
        person = TrackedPerson.objects.get(pk=pk, user=request.user)
    except TrackedPerson.DoesNotExist:
        return JsonResponse({'error': 'Person not found'}, status=404)

    return JsonResponse({
        'id': person.pk,
        'name': person.name,
        'relationship': person.relationship,
        'sentiment': person.sentiment,
        'notes': person.notes,
        'mention_count': person.mention_count,
        'first_mention_date': person.first_mention_date.isoformat() if person.first_mention_date else None,
        'last_mention_date': person.last_mention_date.isoformat() if person.last_mention_date else None,
        'relationships': TrackedPerson.RELATIONSHIP_CHOICES,
        'sentiments': TrackedPerson.SENTIMENT_CHOICES,
    })


@login_required
@require_http_methods(["POST"])
def person_update(request, pk):
    """Update person details."""
    from .models import TrackedPerson
    import json

    try:
        person = TrackedPerson.objects.get(pk=pk, user=request.user)
    except TrackedPerson.DoesNotExist:
        return JsonResponse({'error': 'Person not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Update allowed fields
    if 'name' in data and data['name'].strip():
        person.name = data['name'].strip()
        person.normalized_name = data['name'].strip().lower()
    if 'relationship' in data:
        person.relationship = data['relationship']
    if 'sentiment' in data:
        person.sentiment = data['sentiment']
    if 'notes' in data:
        person.notes = data['notes']

    person.save()

    return JsonResponse({
        'success': True,
        'person': {
            'id': person.pk,
            'name': person.name,
            'relationship': person.relationship,
            'relationship_display': person.get_relationship_display(),
            'sentiment': person.sentiment,
            'sentiment_display': person.get_sentiment_display(),
            'notes': person.notes,
        }
    })


@login_required
@require_http_methods(["POST"])
def person_delete(request, pk):
    """Delete a tracked person."""
    from .models import TrackedPerson

    try:
        person = TrackedPerson.objects.get(pk=pk, user=request.user)
    except TrackedPerson.DoesNotExist:
        return JsonResponse({'error': 'Person not found'}, status=404)

    person.delete()
    return JsonResponse({'success': True})


# =============================================================================
# Book API Endpoints
# =============================================================================

@login_required
@premium_required
def book_detail(request, pk):
    """Get book details for edit modal."""
    from .models import TrackedBook

    try:
        book = TrackedBook.objects.get(pk=pk, user=request.user)
    except TrackedBook.DoesNotExist:
        return JsonResponse({'error': 'Book not found'}, status=404)

    return JsonResponse({
        'id': book.pk,
        'title': book.title,
        'author': book.author,
        'status': book.status,
        'rating': book.rating,
        'current_page': book.current_page,
        'total_pages': book.total_pages,
        'started_date': book.started_date.isoformat() if book.started_date else None,
        'finished_date': book.finished_date.isoformat() if book.finished_date else None,
    })


@login_required
@require_http_methods(["POST"])
def book_update(request, pk):
    """Update book details."""
    from .models import TrackedBook
    import json
    from datetime import date

    try:
        book = TrackedBook.objects.get(pk=pk, user=request.user)
    except TrackedBook.DoesNotExist:
        return JsonResponse({'error': 'Book not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Update allowed fields
    if 'title' in data and data['title'].strip():
        book.title = data['title'].strip()
        book.normalized_title = data['title'].strip().lower()
    if 'author' in data:
        book.author = data['author'].strip()
        book.normalized_author = data['author'].strip().lower()
    if 'status' in data:
        book.status = data['status']
        # Auto-set finished_date when marking as finished
        if data['status'] == 'finished' and not book.finished_date:
            book.finished_date = date.today()
    if 'rating' in data:
        book.rating = int(data['rating']) if data['rating'] else None
    if 'current_page' in data:
        book.current_page = int(data['current_page']) if data['current_page'] else 0
    if 'total_pages' in data:
        book.total_pages = int(data['total_pages']) if data['total_pages'] else None
    if 'started_date' in data:
        book.started_date = data['started_date'] if data['started_date'] else None
    if 'finished_date' in data:
        book.finished_date = data['finished_date'] if data['finished_date'] else None

    book.save()

    return JsonResponse({
        'success': True,
        'book': {
            'id': book.pk,
            'title': book.title,
            'author': book.author,
            'status': book.status,
            'status_display': book.get_status_display(),
            'rating': book.rating,
        }
    })


@login_required
@require_http_methods(["POST"])
def book_delete(request, pk):
    """Delete a tracked book."""
    from .models import TrackedBook

    try:
        book = TrackedBook.objects.get(pk=pk, user=request.user)
    except TrackedBook.DoesNotExist:
        return JsonResponse({'error': 'Book not found'}, status=404)

    book.delete()
    return JsonResponse({'success': True})


# =============================================================================
# Media (Movies/Shows) API Endpoints
# =============================================================================

@login_required
@premium_required
def media_detail(request, pk):
    """Get media capture details for edit modal."""
    from apps.journal.models import EntryCapture

    try:
        media = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='watched')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Media not found'}, status=404)

    return JsonResponse({
        'id': media.pk,
        'title': media.data.get('title', ''),
        'type': media.data.get('type', 'movie'),
        'rating': media.data.get('rating'),
        'notes': media.data.get('notes', ''),
        'entry_date': media.entry.entry_date.isoformat(),
    })


@login_required
@require_http_methods(["POST"])
def media_update(request, pk):
    """Update media capture details."""
    from apps.journal.models import EntryCapture
    import json

    try:
        media = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='watched')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Media not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Update the data JSON field
    if 'title' in data:
        media.data['title'] = data['title'].strip()
    if 'type' in data:
        media.data['type'] = data['type']
    if 'rating' in data:
        media.data['rating'] = int(data['rating']) if data['rating'] else None
    if 'notes' in data:
        media.data['notes'] = data['notes']

    media.save()

    return JsonResponse({
        'success': True,
        'media': {
            'id': media.pk,
            'title': media.data.get('title', ''),
            'type': media.data.get('type', 'movie'),
            'rating': media.data.get('rating'),
        }
    })


@login_required
@require_http_methods(["POST"])
def media_delete(request, pk):
    """Delete a media capture."""
    from apps.journal.models import EntryCapture

    try:
        media = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='watched')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Media not found'}, status=404)

    media.delete()
    return JsonResponse({'success': True})


# =============================================================================
# Workout API Endpoints
# =============================================================================

@login_required
@premium_required
def workout_detail(request, pk):
    """Get workout capture details for edit modal."""
    from apps.journal.models import EntryCapture

    try:
        workout = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='workout')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Workout not found'}, status=404)

    return JsonResponse({
        'id': workout.pk,
        'type': workout.data.get('type', 'workout'),
        'duration': workout.data.get('duration'),
        'intensity': workout.data.get('intensity', 'medium'),
        'notes': workout.data.get('notes', ''),
        'entry_date': workout.entry.entry_date.isoformat(),
    })


@login_required
@require_http_methods(["POST"])
def workout_update(request, pk):
    """Update workout capture details."""
    from apps.journal.models import EntryCapture
    import json

    try:
        workout = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='workout')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Workout not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Update the data JSON field
    if 'type' in data:
        workout.data['type'] = data['type'].strip().lower()
    if 'duration' in data:
        workout.data['duration'] = int(data['duration']) if data['duration'] else None
    if 'intensity' in data:
        workout.data['intensity'] = data['intensity']
    if 'notes' in data:
        workout.data['notes'] = data['notes']

    workout.save()

    return JsonResponse({
        'success': True,
        'workout': {
            'id': workout.pk,
            'type': workout.data.get('type', 'workout'),
            'duration': workout.data.get('duration'),
            'intensity': workout.data.get('intensity', 'medium'),
        }
    })


@login_required
@require_http_methods(["POST"])
def workout_delete(request, pk):
    """Delete a workout capture."""
    from apps.journal.models import EntryCapture

    try:
        workout = EntryCapture.objects.get(pk=pk, entry__user=request.user, capture_type='workout')
    except EntryCapture.DoesNotExist:
        return JsonResponse({'error': 'Workout not found'}, status=404)

    workout.delete()
    return JsonResponse({'success': True})


@login_required
@premium_required
def fitness_dashboard(request):
    """Workout analytics with heatmaps."""
    from apps.journal.models import EntryCapture

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    workouts = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='workout',
        entry__entry_date__year=year
    ).select_related('entry').order_by('-entry__entry_date')

    # Heatmap data (date -> count)
    heatmap_data = {}
    by_type = {}
    by_intensity = {}
    total_duration = 0
    monthly_counts = [0] * 12

    for w in workouts:
        date_str = w.entry.entry_date.isoformat()
        heatmap_data[date_str] = heatmap_data.get(date_str, 0) + 1

        wtype = w.data.get('type', 'other')
        duration = w.data.get('duration', 0)
        if isinstance(duration, (int, float)):
            total_duration += duration

        if wtype not in by_type:
            by_type[wtype] = {'count': 0, 'duration': 0}
        by_type[wtype]['count'] += 1
        by_type[wtype]['duration'] += duration if isinstance(duration, (int, float)) else 0

        intensity = w.data.get('intensity', 'medium')
        by_intensity[intensity] = by_intensity.get(intensity, 0) + 1

        # Monthly
        monthly_counts[w.entry.entry_date.month - 1] += 1

    # Get available years
    years_with_workouts = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='workout'
    ).dates('entry__entry_date', 'year').values_list('entry__entry_date__year', flat=True)
    available_years = sorted(set(years_with_workouts), reverse=True) if years_with_workouts else [now.year]

    return render(request, 'dashboard/captures/fitness.html', {
        'year': year,
        'available_years': available_years,
        'workouts': workouts[:50],  # Limit for display
        'heatmap_data': heatmap_data,
        'by_type': by_type,
        'by_intensity': by_intensity,
        'monthly_counts': monthly_counts,
        'total_workouts': workouts.count(),
        'total_duration': total_duration,
        'avg_duration': round(total_duration / workouts.count(), 1) if workouts.count() else 0,
        'current_year': year,
        'active_page': 'fitness',
    })


@login_required
@premium_required
def travel_dashboard(request):
    """Travel and places analytics."""
    from apps.journal.models import EntryCapture

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    # Get all travel captures
    travels = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='travel',
        entry__entry_date__year=year
    ).select_related('entry').order_by('-entry__entry_date')

    # Get all place captures
    places = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='place',
        entry__entry_date__year=year
    ).select_related('entry').order_by('-entry__entry_date')

    # Travel stats
    by_mode = {}
    destinations = {}
    monthly_travels = [0] * 12

    for t in travels:
        mode = t.data.get('mode', 'other')
        by_mode[mode] = by_mode.get(mode, 0) + 1

        dest = t.data.get('destination', '')
        if dest:
            destinations[dest] = destinations.get(dest, 0) + 1

        monthly_travels[t.entry.entry_date.month - 1] += 1

    # Place stats
    by_place_type = {}
    place_visits = {}
    monthly_places = [0] * 12

    for p in places:
        place_type = p.data.get('type', 'other')
        by_place_type[place_type] = by_place_type.get(place_type, 0) + 1

        name = p.data.get('name', '')
        if name:
            place_visits[name] = place_visits.get(name, 0) + 1

        monthly_places[p.entry.entry_date.month - 1] += 1

    # Sort destinations and places by visit count
    top_destinations = sorted(destinations.items(), key=lambda x: x[1], reverse=True)[:10]
    top_places = sorted(place_visits.items(), key=lambda x: x[1], reverse=True)[:10]

    # Get available years
    travel_years = EntryCapture.objects.filter(
        entry__user=user,
        capture_type__in=['travel', 'place']
    ).dates('entry__entry_date', 'year').values_list('entry__entry_date__year', flat=True)
    available_years = sorted(set(travel_years), reverse=True) if travel_years else [now.year]

    return render(request, 'dashboard/captures/travel.html', {
        'year': year,
        'available_years': available_years,
        'travels': travels[:30],
        'places': places[:30],
        'by_mode': by_mode,
        'by_place_type': by_place_type,
        'top_destinations': top_destinations,
        'top_places': top_places,
        'monthly_travels': monthly_travels,
        'monthly_places': monthly_places,
        'total_travels': travels.count(),
        'total_places': places.count(),
        'active_page': 'travel',
    })


@login_required
@premium_required
def wellness_dashboard(request):
    """Wellness analytics - meals, dreams, and gratitude."""
    from apps.journal.models import Entry, EntryCapture
    import re

    user = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))

    # Get all entries for the year
    entries = Entry.objects.filter(
        user=user,
        entry_date__year=year
    ).select_related('analysis').order_by('-entry_date')

    # Find entries with dream blocks
    dream_pattern = re.compile(r'\{dream\}.*?\{/dream\}', re.DOTALL | re.IGNORECASE)
    dream_entries = []
    for entry in entries:
        if entry.content and dream_pattern.search(entry.content):
            dream_entries.append(entry)

    # Find entries with gratitude blocks
    gratitude_pattern = re.compile(r'\{gratitude\}.*?\{/gratitude\}', re.DOTALL | re.IGNORECASE)
    gratitude_entries = []
    for entry in entries:
        if entry.content and gratitude_pattern.search(entry.content):
            gratitude_entries.append(entry)

    # Get meal captures
    meals = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='meal',
        entry__entry_date__year=year
    ).select_related('entry').order_by('-entry__entry_date')

    # Meal stats
    meal_types = {}
    monthly_meals = [0] * 12
    for meal in meals:
        meal_type = meal.data.get('type', 'other')
        meal_types[meal_type] = meal_types.get(meal_type, 0) + 1
        monthly_meals[meal.entry.entry_date.month - 1] += 1

    # Monthly dream/gratitude counts
    monthly_dreams = [0] * 12
    monthly_gratitude = [0] * 12

    for entry in dream_entries:
        monthly_dreams[entry.entry_date.month - 1] += 1

    for entry in gratitude_entries:
        monthly_gratitude[entry.entry_date.month - 1] += 1

    # Get available years
    years_with_data = set()
    for entry in Entry.objects.filter(user=user):
        if entry.content:
            if dream_pattern.search(entry.content) or gratitude_pattern.search(entry.content):
                years_with_data.add(entry.entry_date.year)

    meal_years = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='meal'
    ).dates('entry__entry_date', 'year').values_list('entry__entry_date__year', flat=True)
    years_with_data.update(meal_years)

    available_years = sorted(years_with_data, reverse=True) if years_with_data else [now.year]

    return render(request, 'dashboard/captures/wellness.html', {
        'year': year,
        'available_years': available_years,
        'dream_entries': dream_entries[:30],
        'gratitude_entries': gratitude_entries[:30],
        'meals': meals[:30],
        'meal_types': meal_types,
        'monthly_dreams': monthly_dreams,
        'monthly_gratitude': monthly_gratitude,
        'monthly_meals': monthly_meals,
        'total_dreams': len(dream_entries),
        'total_gratitude': len(gratitude_entries),
        'total_meals': meals.count(),
        'active_page': 'wellness',
    })


@login_required
@require_http_methods(["GET"])
def moon_phase_entries(request, phase):
    """Get entries for a specific moon phase."""
    from apps.journal.models import Entry
    from apps.analytics.services.moon import MOON_PHASE_DISPLAY

    user = request.user
    days = int(request.GET.get('days', 180))
    start_date = timezone.now().date() - timedelta(days=days)

    # Validate phase
    valid_phases = ['new_moon', 'waxing_crescent', 'first_quarter', 'waxing_gibbous',
                    'full_moon', 'waning_gibbous', 'last_quarter', 'waning_crescent']
    if phase not in valid_phases:
        return JsonResponse({'error': 'Invalid moon phase'}, status=400)

    # Get entries for this phase
    entries = Entry.objects.filter(
        user=user,
        entry_date__gte=start_date,
        is_analyzed=True,
        analysis__moon_phase=phase
    ).select_related('analysis').order_by('-entry_date')

    # Format entries for response
    entries_data = []
    for entry in entries:
        entries_data.append({
            'id': entry.pk,
            'date': entry.entry_date.strftime('%b %d, %Y'),
            'title': entry.title or entry.entry_date.strftime('%A, %B %d'),
            'preview': entry.preview[:150] + '...' if len(entry.preview) > 150 else entry.preview,
            'mood': entry.analysis.detected_mood if hasattr(entry, 'analysis') else '',
            'mood_emoji': get_mood_emoji(entry.analysis.detected_mood) if hasattr(entry, 'analysis') else '',
            'sentiment': round(entry.analysis.sentiment_score, 2) if hasattr(entry, 'analysis') else 0,
            'url': f'/journal/{entry.pk}/',
        })

    return JsonResponse({
        'phase': phase,
        'display_name': MOON_PHASE_DISPLAY.get(phase, phase.replace('_', ' ').title()),
        'count': len(entries_data),
        'entries': entries_data,
    })


def get_mood_emoji(mood):
    """Get emoji for a mood."""
    emojis = {
        'ecstatic': '🤩',
        'happy': '😊',
        'neutral': '😐',
        'sad': '😢',
        'angry': '😠',
    }
    return emojis.get(mood, '')


@login_required
@require_http_methods(["GET"])
def weather_condition_entries(request, condition):
    """Get entries for a specific weather condition."""
    from apps.journal.models import Entry
    from apps.analytics.services.weather import WEATHER_DISPLAY

    user = request.user
    days = int(request.GET.get('days', 180))
    start_date = timezone.now().date() - timedelta(days=days)

    # Valid weather conditions
    valid_conditions = ['clear', 'clouds', 'rain', 'drizzle', 'thunderstorm',
                        'snow', 'mist', 'fog', 'haze']
    if condition not in valid_conditions:
        return JsonResponse({'error': 'Invalid weather condition'}, status=400)

    # Get entries for this weather condition
    entries = Entry.objects.filter(
        user=user,
        entry_date__gte=start_date,
        is_analyzed=True,
        analysis__weather_condition=condition
    ).select_related('analysis').order_by('-entry_date')

    # Format entries for response
    entries_data = []
    for entry in entries:
        temp = None
        if hasattr(entry, 'analysis') and entry.analysis.temperature is not None:
            # Convert to user's preferred unit
            temp_c = entry.analysis.temperature
            if user.profile.temperature_unit == 'F':
                temp = round((temp_c * 9/5) + 32)
            else:
                temp = round(temp_c)

        entries_data.append({
            'id': entry.pk,
            'date': entry.entry_date.strftime('%b %d, %Y'),
            'title': entry.title or entry.entry_date.strftime('%A, %B %d'),
            'preview': entry.preview[:150] + '...' if len(entry.preview) > 150 else entry.preview,
            'mood': entry.analysis.detected_mood if hasattr(entry, 'analysis') else '',
            'mood_emoji': get_mood_emoji(entry.analysis.detected_mood) if hasattr(entry, 'analysis') else '',
            'sentiment': round(entry.analysis.sentiment_score, 2) if hasattr(entry, 'analysis') else 0,
            'temperature': temp,
            'temp_unit': user.profile.temperature_unit,
            'url': f'/journal/{entry.pk}/',
        })

    return JsonResponse({
        'condition': condition,
        'display_name': WEATHER_DISPLAY.get(condition, condition.title()),
        'count': len(entries_data),
        'entries': entries_data,
    })
