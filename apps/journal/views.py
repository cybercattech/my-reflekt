import json
import calendar
from collections import Counter, defaultdict
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, F
from django.db.models.functions import ExtractYear
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings
from .models import Entry, Attachment, EntryCapture
from .forms import EntryForm
from .prompts import get_daily_prompt
from apps.analytics.services.mood import MOOD_EMOJIS


def home(request):
    """Landing page for logged-out users, redirect for logged-in."""
    if request.user.is_authenticated:
        return redirect('journal:entry_list')

    # Get latest 6 published blog posts for the home page
    from apps.blog.models import Post
    blog_posts = Post.objects.filter(status='published').order_by('-published_at')[:6]

    return render(request, 'journal/home.html', {
        'blog_posts': blog_posts,
    })


def features(request):
    """Features explanation page - how AI and POV sharing work."""
    return render(request, 'features.html')


@login_required
def entry_list(request):
    """List all journal entries for the current user."""
    entries = Entry.objects.filter(user=request.user)

    # Search (in-memory for encrypted content)
    query = request.GET.get('q', '')
    if query:
        # With per-user encryption, we need to search in memory
        # Load all user entries and filter those matching the query
        query_lower = query.lower()
        matching_ids = []

        # Get all entries for this user (content is decrypted via middleware)
        for entry in Entry.objects.filter(user=request.user).only('id', 'title', 'content'):
            # Check if query matches title or content
            title = entry.title or ''
            content = entry.content or ''

            # Handle case where decryption fails (returns encrypted gibberish)
            if query_lower in title.lower() or query_lower in content.lower():
                matching_ids.append(entry.id)

        # Filter entries to only those matching search
        entries = entries.filter(id__in=matching_ids)

    # Filter by mood
    mood = request.GET.get('mood', '')
    if mood:
        entries = entries.filter(mood=mood)

    # Filter by capture type (for sidebar navigation)
    filter_type = request.GET.get('type', '')
    if filter_type:
        # Get entries that have captures of this type
        entries = entries.filter(captures__capture_type=filter_type).distinct()

    # Filter by date (for calendar click)
    selected_date = request.GET.get('date', '')
    same_day_other_years = []
    filter_date = None
    if selected_date:
        try:
            filter_date = date.fromisoformat(selected_date)
            entries = entries.filter(entry_date=filter_date)

            # Find entries on the same month/day but different years
            same_day_other_years = Entry.objects.filter(
                user=request.user,
                entry_date__month=filter_date.month,
                entry_date__day=filter_date.day
            ).exclude(entry_date__year=filter_date.year).order_by('-entry_date')
        except ValueError:
            pass

    # Calendar data - generate months from first entry to one month ahead
    today = date.today()
    cal_year, cal_month = today.year, today.month

    # Find the user's earliest entry date
    earliest_entry = Entry.objects.filter(user=request.user).order_by('entry_date').first()
    if earliest_entry:
        start_year = earliest_entry.entry_date.year
        start_month = earliest_entry.entry_date.month
    else:
        # No entries yet - just show current month and next
        start_year = today.year
        start_month = today.month

    # End date is one month ahead of current
    end_month = today.month + 1
    end_year = today.year
    if end_month > 12:
        end_month = 1
        end_year += 1

    # Get all entry dates for the user (we need all of them for the full range)
    entry_dates = set(
        Entry.objects.filter(user=request.user).values_list('entry_date', flat=True)
    )

    # Build list of months with their calendar data
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    calendar_months = []

    current_year = start_year
    current_month = start_month

    # Generate months from start to end (one month ahead)
    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        month_data = {
            'year': current_year,
            'month': current_month,
            'month_name': calendar.month_name[current_month],
            'weeks': []
        }

        for week in cal.monthdatescalendar(current_year, current_month):
            week_data = []
            for day in week:
                week_data.append({
                    'date': day,
                    'day': day.day,
                    'in_month': day.month == current_month,
                    'is_today': day == today,
                    'has_entry': day in entry_dates,
                })
            month_data['weeks'].append(week_data)

        calendar_months.append(month_data)

        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    # Keep these for backward compatibility
    prev_month = cal_month - 1 if cal_month > 1 else 12
    prev_year = cal_year if cal_month > 1 else cal_year - 1
    next_month = cal_month + 1 if cal_month < 12 else 1
    next_year = cal_year if cal_month < 12 else cal_year + 1

    # Include related analysis and tags for the entries list
    entries = entries.select_related('analysis').prefetch_related('tags')

    # Pagination
    paginator = Paginator(entries, 20)
    page = request.GET.get('page', 1)
    entries = paginator.get_page(page)

    # For HTMX partial updates
    if request.htmx:
        return render(request, 'journal/partials/entry_list.html', {'entries': entries})

    # 30-day stats for sidebar
    thirty_days_ago = today - timedelta(days=30)
    recent_entries = Entry.objects.filter(
        user=request.user,
        entry_date__gte=thirty_days_ago
    ).select_related('analysis')

    # Writing mood stats (user-selected mood)
    writing_moods = recent_entries.exclude(mood='').values('mood').annotate(
        count=Count('mood')
    ).order_by('-count')

    writing_moods_list = list(writing_moods[:5])
    max_mood_count = writing_moods_list[0]['count'] if writing_moods_list else 1

    writing_mood_stats = [
        {
            'mood': m['mood'],
            'emoji': MOOD_EMOJIS.get(m['mood'], ''),
            'count': m['count'],
            'label': m['mood'].title(),
            'percentage': round((m['count'] / max_mood_count) * 100)
        }
        for m in writing_moods_list
    ]

    # Perceived mood stats (AI-detected mood from analysis)
    perceived_moods = Counter()
    all_themes = Counter()
    all_keywords = Counter()

    for entry in recent_entries:
        if hasattr(entry, 'analysis') and entry.analysis:
            if entry.analysis.detected_mood:
                perceived_moods[entry.analysis.detected_mood] += 1
            if entry.analysis.themes:
                all_themes.update(entry.analysis.themes)
            if entry.analysis.keywords:
                all_keywords.update(entry.analysis.keywords)

    perceived_mood_stats = [
        {
            'mood': mood_name,
            'emoji': MOOD_EMOJIS.get(mood_name, '😐'),
            'count': count,
            'label': mood_name.title()
        }
        for mood_name, count in perceived_moods.most_common(5)
    ]

    # Top themes and keywords
    top_themes = [{'name': t, 'count': c} for t, c in all_themes.most_common(8)]
    top_keywords = [{'name': k, 'count': c} for k, c in all_keywords.most_common(10)]

    # Show all entries toggle
    show_all = request.GET.get('show_all', '') == '1'

    # Daily writing prompt
    daily_prompt = get_daily_prompt()

    # Count unanalyzed entries
    unanalyzed_count = Entry.objects.filter(user=request.user, is_analyzed=False).count()

    # Year-over-year statistics
    from apps.analytics.models import EntryAnalysis
    import re

    # Calculate overall current streak and best streak
    all_entry_dates = set(
        Entry.objects.filter(user=request.user).values_list('entry_date', flat=True)
    )

    # Current streak (how many consecutive days including today or yesterday)
    current_streak = 0
    check_date = today
    # If no entry today, start from yesterday
    if check_date not in all_entry_dates:
        check_date = today - timedelta(days=1)
    while check_date in all_entry_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Best streak ever
    best_streak = 0
    if all_entry_dates:
        sorted_dates = sorted(all_entry_dates)
        streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                streak += 1
            else:
                best_streak = max(best_streak, streak)
                streak = 1
        best_streak = max(best_streak, streak)

    yearly_stats = []
    years_with_entries = Entry.objects.filter(user=request.user).annotate(
        year=ExtractYear('entry_date')
    ).values('year').distinct().order_by('-year')

    for year_data in years_with_entries:
        year = year_data['year']
        year_entries = Entry.objects.filter(
            user=request.user,
            entry_date__year=year
        ).select_related('analysis')

        entry_count = year_entries.count()
        total_words = year_entries.aggregate(total=Sum('word_count'))['total'] or 0

        # Best streak for this year
        year_dates = set(year_entries.values_list('entry_date', flat=True))
        year_best_streak = 0
        if year_dates:
            sorted_year_dates = sorted(year_dates)
            streak = 1
            for i in range(1, len(sorted_year_dates)):
                if (sorted_year_dates[i] - sorted_year_dates[i-1]).days == 1:
                    streak += 1
                else:
                    year_best_streak = max(year_best_streak, streak)
                    streak = 1
            year_best_streak = max(year_best_streak, streak)

        # Mood distribution - combine user-selected and AI-detected moods
        mood_distribution = Counter()

        # Sentiment and themes from analysis
        analyzed_entries = year_entries.filter(is_analyzed=True)
        avg_sentiment = 0
        sentiment_label = 'neutral'
        themes_counter = Counter()
        keywords_counter = Counter()
        positive_sentiment_count = 0
        negative_sentiment_count = 0
        neutral_sentiment_count = 0

        for entry in analyzed_entries:
            if hasattr(entry, 'analysis') and entry.analysis:
                # Use sentiment for positive/negative calculation
                score = entry.analysis.sentiment_score
                avg_sentiment += score
                if score > 0.1:
                    positive_sentiment_count += 1
                elif score < -0.1:
                    negative_sentiment_count += 1
                else:
                    neutral_sentiment_count += 1

                # Collect detected moods (AI-analyzed)
                detected = entry.analysis.detected_mood
                if detected:
                    mood_distribution[detected] += 1

                # Collect themes and keywords
                for theme in entry.analysis.themes or []:
                    themes_counter[theme] += 1
                for keyword in entry.analysis.keywords or []:
                    keywords_counter[keyword] += 1

        # Find dominant mood (based on AI-detected moods only, for consistency with sentiment)
        dominant_mood = ''
        if mood_distribution:
            dominant_mood = mood_distribution.most_common(1)[0][0]

        analyzed_count = analyzed_entries.count()
        if analyzed_count > 0:
            avg_sentiment = avg_sentiment / analyzed_count
            if avg_sentiment > 0.1:
                sentiment_label = 'positive'
            elif avg_sentiment < -0.1:
                sentiment_label = 'negative'

        # Extract hashtags from content for this year
        hashtag_counter = Counter()
        for entry in year_entries:
            tags = re.findall(r'(?:^|\s)#([a-zA-Z][a-zA-Z0-9_]*)', entry.content)
            for tag in tags:
                hashtag_counter[tag.lower()] += 1

        # Calculate positive vs negative percentage based on sentiment analysis
        total_analyzed = positive_sentiment_count + negative_sentiment_count + neutral_sentiment_count
        if total_analyzed > 0:
            positive_percent = round((positive_sentiment_count / total_analyzed) * 100)
            negative_percent = round((negative_sentiment_count / total_analyzed) * 100)
        else:
            positive_percent = 0
            negative_percent = 0

        # Convert mood_distribution Counter to dict for template
        mood_dist_dict = dict(mood_distribution)

        yearly_stats.append({
            'year': year,
            'entry_count': entry_count,
            'total_words': total_words,
            'avg_words': round(total_words / entry_count) if entry_count else 0,
            'best_streak': year_best_streak,
            'mood_distribution': mood_dist_dict,
            'dominant_mood': dominant_mood,
            'dominant_mood_emoji': MOOD_EMOJIS.get(dominant_mood, '😐'),
            'avg_sentiment': round(avg_sentiment, 2),
            'sentiment_label': sentiment_label,
            'top_themes': themes_counter.most_common(5),
            'top_keywords': keywords_counter.most_common(5),
            'top_hashtags': hashtag_counter.most_common(5),
            # Sentiment-based percentages (from analysis)
            'positive_percent': positive_percent,
            'negative_percent': negative_percent,
            'neutral_percent': 100 - positive_percent - negative_percent if total_analyzed > 0 else 0,
            # Counts for display
            'positive_count': positive_sentiment_count,
            'negative_count': negative_sentiment_count,
            'neutral_count': neutral_sentiment_count,
            'analyzed_count': analyzed_count,
            'analyzed_percent': round((analyzed_count / entry_count) * 100) if entry_count else 0,
        })

    # Daily Devotion (if enabled)
    daily_devotion = None
    has_entry_today = False
    if request.user.profile.devotion_enabled:
        from apps.analytics.services.devotion import get_daily_devotion
        daily_devotion = get_daily_devotion()
        # Check if user has an entry for today
        has_entry_today = Entry.objects.filter(user=request.user, entry_date=today).exists()

    # === NEW INSIGHTS DATA ===

    # Journaled days this year and this month
    this_year_entries = Entry.objects.filter(
        user=request.user,
        entry_date__year=today.year
    )
    journaled_days_year = this_year_entries.values('entry_date').distinct().count()
    journaled_days_month = Entry.objects.filter(
        user=request.user,
        entry_date__year=today.year,
        entry_date__month=today.month
    ).values('entry_date').distinct().count()

    # Word counts this month and this year
    words_this_month = Entry.objects.filter(
        user=request.user,
        entry_date__year=today.year,
        entry_date__month=today.month
    ).aggregate(total=Sum('word_count'))['total'] or 0

    words_this_year = this_year_entries.aggregate(total=Sum('word_count'))['total'] or 0

    # Monthly entry counts for bar chart (current year)
    monthly_entry_counts = []
    for month_num in range(1, 13):
        count = Entry.objects.filter(
            user=request.user,
            entry_date__year=today.year,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts.append(count)

    # Total entries this year
    entries_this_year = sum(monthly_entry_counts)

    # Monthly entry counts for previous year
    prev_year = today.year - 1
    monthly_entry_counts_prev_year = []
    for month_num in range(1, 13):
        count = Entry.objects.filter(
            user=request.user,
            entry_date__year=prev_year,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts_prev_year.append(count)
    entries_prev_year = sum(monthly_entry_counts_prev_year)

    # Monthly entry counts for all-time (sum across all years by month)
    monthly_entry_counts_all_time = []
    for month_num in range(1, 13):
        count = Entry.objects.filter(
            user=request.user,
            entry_date__month=month_num
        ).count()
        monthly_entry_counts_all_time.append(count)
    entries_all_time = Entry.objects.filter(user=request.user).count()

    # Longest weekly streak (consecutive weeks with at least 1 entry)
    longest_weekly_streak = 0
    if all_entry_dates:
        # Get unique weeks (year, week_number) for all entries
        weeks_with_entries = set()
        for entry_date in all_entry_dates:
            iso_cal = entry_date.isocalendar()
            weeks_with_entries.add((iso_cal[0], iso_cal[1]))  # (year, week)

        # Sort weeks and find longest consecutive streak
        sorted_weeks = sorted(weeks_with_entries)
        if sorted_weeks:
            weekly_streak = 1
            for i in range(1, len(sorted_weeks)):
                prev_year, prev_week = sorted_weeks[i-1]
                curr_year, curr_week = sorted_weeks[i]

                # Check if consecutive week
                if curr_year == prev_year and curr_week == prev_week + 1:
                    weekly_streak += 1
                elif curr_year == prev_year + 1 and prev_week >= 52 and curr_week == 1:
                    # Year transition (week 52/53 to week 1)
                    weekly_streak += 1
                else:
                    longest_weekly_streak = max(longest_weekly_streak, weekly_streak)
                    weekly_streak = 1
            longest_weekly_streak = max(longest_weekly_streak, weekly_streak)

    # Map locations from travel and place captures
    from apps.journal.services.geocoding import get_map_locations_for_user
    map_locations = get_map_locations_for_user(request.user)
    total_places = len(map_locations)

    # Highest earned badge
    from apps.accounts.models import UserBadge
    earned_badges = UserBadge.get_user_badges(request.user)
    # Get the highest badge (most days required)
    highest_badge = max(earned_badges, key=lambda b: b['days']) if earned_badges else None

    return render(request, 'journal/entry_list.html', {
        'show_all': show_all,
        'daily_prompt': daily_prompt,
        'entries': entries,
        'query': query,
        'mood': mood,
        'filter_type': filter_type,
        'selected_date': selected_date,
        'filter_date': filter_date,
        'same_day_other_years': same_day_other_years,
        'calendar_months': calendar_months,
        'cal_year': cal_year,
        'cal_month': cal_month,
        'cal_month_name': calendar.month_name[cal_month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'writing_mood_stats': writing_mood_stats,
        'perceived_mood_stats': perceived_mood_stats,
        'top_themes': top_themes,
        'top_keywords': top_keywords,
        'unanalyzed_count': unanalyzed_count,
        'yearly_stats': yearly_stats,
        'current_streak': current_streak,
        'best_streak': best_streak,
        # Daily devotion
        'daily_devotion': daily_devotion,
        'has_entry_today': has_entry_today,
        # New insight data
        'journaled_days_year': journaled_days_year,
        'journaled_days_month': journaled_days_month,
        'words_this_month': words_this_month,
        'words_this_year': words_this_year,
        'monthly_entry_counts': monthly_entry_counts,
        'monthly_entry_counts_prev_year': monthly_entry_counts_prev_year,
        'monthly_entry_counts_all_time': monthly_entry_counts_all_time,
        'entries_this_year': entries_this_year,
        'entries_prev_year': entries_prev_year,
        'entries_all_time': entries_all_time,
        'prev_year': prev_year,
        'longest_weekly_streak': longest_weekly_streak,
        'map_locations': map_locations,
        'total_places': total_places,
        'highest_badge': highest_badge,
    })


def get_sidebar_context(user):
    """Get common sidebar context for calendar and stats."""
    today = date.today()
    cal_year, cal_month = today.year, today.month

    # Find the user's earliest entry date for continuous scroll
    earliest_entry = Entry.objects.filter(user=user).order_by('entry_date').first()
    if earliest_entry:
        start_year = earliest_entry.entry_date.year
        start_month = earliest_entry.entry_date.month
    else:
        start_year = today.year
        start_month = today.month

    # End date is one month ahead of current
    end_month = today.month + 1
    end_year = today.year
    if end_month > 12:
        end_month = 1
        end_year += 1

    # Get all entry dates for the user
    entry_dates = set(
        Entry.objects.filter(user=user).values_list('entry_date', flat=True)
    )

    # Build list of months with their calendar data
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    calendar_months = []

    current_year = start_year
    current_month = start_month

    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        month_data = {
            'year': current_year,
            'month': current_month,
            'month_name': calendar.month_name[current_month],
            'weeks': []
        }

        for week in cal.monthdatescalendar(current_year, current_month):
            week_data = []
            for day in week:
                week_data.append({
                    'date': day,
                    'day': day.day,
                    'in_month': day.month == current_month,
                    'is_today': day == today,
                    'has_entry': day in entry_dates,
                })
            month_data['weeks'].append(week_data)

        calendar_months.append(month_data)

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    # 30-day stats
    thirty_days_ago = today - timedelta(days=30)
    recent_entries = Entry.objects.filter(
        user=user,
        entry_date__gte=thirty_days_ago
    ).select_related('analysis')

    writing_moods = recent_entries.exclude(mood='').values('mood').annotate(
        count=Count('mood')
    ).order_by('-count')[:5]

    writing_moods_list = list(writing_moods)
    max_mood_count = writing_moods_list[0]['count'] if writing_moods_list else 1

    writing_mood_stats = [
        {'mood': m['mood'], 'emoji': MOOD_EMOJIS.get(m['mood'], ''),
         'count': m['count'], 'label': m['mood'].title(),
         'percentage': round((m['count'] / max_mood_count) * 100)}
        for m in writing_moods_list
    ]

    # Perceived mood stats (AI-detected mood from analysis)
    perceived_moods = Counter()
    all_themes = Counter()
    all_keywords = Counter()

    for entry in recent_entries:
        if hasattr(entry, 'analysis') and entry.analysis:
            if entry.analysis.detected_mood:
                perceived_moods[entry.analysis.detected_mood] += 1
            if entry.analysis.themes:
                all_themes.update(entry.analysis.themes)
            if entry.analysis.keywords:
                all_keywords.update(entry.analysis.keywords)

    perceived_mood_stats = [
        {
            'mood': mood_name,
            'emoji': MOOD_EMOJIS.get(mood_name, '😐'),
            'count': count,
            'label': mood_name.title()
        }
        for mood_name, count in perceived_moods.most_common(5)
    ]

    # Top themes and keywords
    top_themes = [{'name': t, 'count': c} for t, c in all_themes.most_common(8)]
    top_keywords = [{'name': k, 'count': c} for k, c in all_keywords.most_common(10)]

    # Daily prompt
    daily_prompt = get_daily_prompt()

    return {
        'calendar_months': calendar_months,
        'cal_year': cal_year,
        'cal_month': cal_month,
        'cal_month_name': calendar.month_name[cal_month],
        'today': today,
        'writing_mood_stats': writing_mood_stats,
        'perceived_mood_stats': perceived_mood_stats,
        'top_themes': top_themes,
        'top_keywords': top_keywords,
        'daily_prompt': daily_prompt,
    }


@login_required
def entry_create(request):
    """Create a new journal entry."""
    # Check for challenge context
    challenge_slug = request.GET.get('challenge') or request.POST.get('challenge_slug')
    challenge_day = request.GET.get('day') or request.POST.get('challenge_day')
    challenge_prompt = None
    user_challenge = None

    if challenge_slug and challenge_day:
        from apps.challenges.models import Challenge, ChallengePrompt, UserChallenge
        try:
            challenge = Challenge.objects.get(slug=challenge_slug)
            challenge_prompt = ChallengePrompt.objects.filter(
                challenge=challenge, day_number=int(challenge_day)
            ).first()
            user_challenge = UserChallenge.objects.filter(
                user=request.user, challenge=challenge, status='active'
            ).first()
        except (Challenge.DoesNotExist, ValueError):
            pass

    if request.method == 'POST':
        form = EntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()

            # Link to challenge if applicable
            if challenge_prompt and user_challenge and request.POST.get('link_challenge') == 'on':
                from apps.challenges.models import ChallengeEntry
                from apps.challenges.services import check_on_time
                ChallengeEntry.objects.get_or_create(
                    user_challenge=user_challenge,
                    prompt=challenge_prompt,
                    defaults={
                        'entry': entry,
                        'is_on_time': check_on_time(user_challenge, challenge_prompt),
                    }
                )

            messages.success(request, 'Entry saved successfully.')
            return redirect('journal:entry_detail', pk=entry.pk)
    else:
        # Check if there's a prompt to pre-fill
        prompt = request.GET.get('prompt', '')
        initial_data = {}

        # Pre-fill with challenge prompt if available
        if challenge_prompt:
            initial_data['content'] = f"**Challenge Prompt:** {challenge_prompt.prompt_text}\n\n"
        elif prompt:
            initial_data['content'] = f"**Prompt:** {prompt}\n\n"

        form = EntryForm(initial=initial_data)

    context = {
        'form': form,
        'is_new': True,
        'editor_preference': request.user.profile.editor_preference,
        'profile': request.user.profile,
        'prompt': request.GET.get('prompt', ''),
        'challenge_prompt': challenge_prompt,
        'user_challenge': user_challenge,
        'challenge_slug': challenge_slug,
        'challenge_day': challenge_day,
    }
    context.update(get_sidebar_context(request.user))

    return render(request, 'journal/entry_form.html', context)


@login_required
def entry_detail(request, pk):
    """View a single journal entry."""
    entry = get_object_or_404(Entry, pk=pk, user=request.user)

    # Find other entries on the same day (month/day) in different years
    same_day_entries = Entry.objects.filter(
        user=request.user,
        entry_date__month=entry.entry_date.month,
        entry_date__day=entry.entry_date.day
    ).exclude(pk=entry.pk).order_by('-entry_date')

    context = {
        'entry': entry,
        'same_day_entries': same_day_entries,
    }
    context.update(get_sidebar_context(request.user))

    return render(request, 'journal/entry_detail.html', context)


@login_required
def entry_edit(request, pk):
    """Edit an existing journal entry."""
    entry = get_object_or_404(Entry, pk=pk, user=request.user)

    if request.method == 'POST':
        form = EntryForm(request.POST, instance=entry)
        if form.is_valid():
            # Reset analysis flag so it gets re-analyzed
            entry = form.save(commit=False)
            entry.is_analyzed = False
            entry.save()
            messages.success(request, 'Entry updated successfully.')
            return redirect('journal:entry_detail', pk=entry.pk)
    else:
        form = EntryForm(instance=entry)

    context = {
        'form': form,
        'entry': entry,
        'is_new': False,
        'editor_preference': request.user.profile.editor_preference,
        'profile': request.user.profile,
    }
    context.update(get_sidebar_context(request.user))

    return render(request, 'journal/entry_form.html', context)


@login_required
def entry_delete(request, pk):
    """Delete a journal entry."""
    entry = get_object_or_404(Entry, pk=pk, user=request.user)

    if request.method == 'POST':
        entry_title = entry.title or entry.entry_date.strftime('%B %d, %Y')
        entry.delete()

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Entry "{entry_title}" deleted.'})

        messages.success(request, 'Entry deleted.')
        return redirect('journal:entry_list')

    return render(request, 'journal/entry_confirm_delete.html', {'entry': entry})


@login_required
@require_POST
def add_devotion_to_entry(request):
    """Add today's devotion to an entry (insert or create new)."""
    action = request.POST.get('action')  # 'insert' or 'create'
    today = date.today()

    if not request.user.profile.devotion_enabled:
        return JsonResponse({'success': False, 'error': 'Devotion feature not enabled'}, status=403)

    # Get today's devotion
    from apps.analytics.services.devotion import get_daily_devotion
    devotion = get_daily_devotion()

    # Format devotion text
    devotion_text = f"""

---

**{devotion['reference']}**

> {devotion['verse']}

{devotion['reflection']}

*Daily Devotion - {devotion['theme']}*

"""

    if action == 'insert':
        # Find today's entry and insert devotion
        entry = Entry.objects.filter(user=request.user, entry_date=today).first()
        if not entry:
            return JsonResponse({'success': False, 'error': 'No entry found for today'}, status=404)

        # Append devotion to existing content
        entry.content = (entry.content or '') + devotion_text
        entry.save()

        # Add #devotion tag
        from .models import Tag
        devotion_tag, created = Tag.objects.get_or_create(
            user=request.user,
            name='devotion'
        )
        devotion_tag.entries.add(entry)

        return JsonResponse({
            'success': True,
            'message': 'Devotion added to today\'s entry',
            'entry_id': entry.pk,
            'redirect_url': reverse('journal:entry_detail', args=[entry.pk])
        })

    elif action == 'create':
        # Create new entry with devotion
        entry = Entry.objects.create(
            user=request.user,
            entry_date=today,
            title=f"Daily Reflection - {devotion['theme']}",
            content=devotion_text.strip()
        )

        # Add #devotion tag
        from .models import Tag
        devotion_tag, created = Tag.objects.get_or_create(
            user=request.user,
            name='devotion'
        )
        devotion_tag.entries.add(entry)

        return JsonResponse({
            'success': True,
            'message': 'New entry created with devotion',
            'entry_id': entry.pk,
            'redirect_url': reverse('journal:entry_detail', args=[entry.pk])
        })

    return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)


@login_required
def entry_at_offset(request):
    """
    Return HTML for a single entry at a given offset.
    Used to refill the entry list after deletion.
    """
    offset = int(request.GET.get('offset', 0))
    query = request.GET.get('q', '')
    mood = request.GET.get('mood', '')

    entries = Entry.objects.filter(user=request.user).order_by('-entry_date', '-created_at')

    if query:
        entries = entries.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )
    if mood:
        entries = entries.filter(mood=mood)

    try:
        entry = entries[offset]
    except IndexError:
        return JsonResponse({'html': None})

    # Build the HTML for the entry row
    mood_emoji = entry.mood_emoji if entry.mood else ''
    title = entry.title if entry.title else entry.entry_date.strftime('%B %d, %Y')
    date_display = entry.entry_date.strftime('%A, %B %d, %Y')

    analysis_badge = ''
    if hasattr(entry, 'analysis') and entry.analysis:
        mood = entry.analysis.detected_mood
        analysis_badge = f'<span class="badge badge-mood-{mood} ms-2">{mood}</span>'

    analyzed_icon = '<i class="bi bi-check-circle text-success" title="Analyzed"></i>' if entry.is_analyzed else '<i class="bi bi-hourglass text-warning" title="Processing..."></i>'

    html = f'''
    <div class="list-group-item entry-card-inner entry-row" data-entry-id="{entry.pk}">
        <div class="d-flex w-100 justify-content-between align-items-start">
            <a href="/journal/{entry.pk}/" class="entry-link flex-grow-1 text-decoration-none">
                <div class="d-flex align-items-center mb-1">
                    {'<span class="mood-emoji me-2">' + mood_emoji + '</span>' if mood_emoji else ''}
                    <h5 class="mb-0 h6 text-dark">{title}</h5>
                </div>
                <p class="text-muted mb-1 small">{date_display}</p>
                <p class="mb-1 small text-dark">{entry.preview}</p>
                <small class="text-muted">{entry.word_count} words</small>
                {analysis_badge}
            </a>
            <div class="entry-actions d-flex align-items-center gap-2">
                {analyzed_icon}
                <button type="button"
                        class="btn btn-sm btn-outline-danger delete-entry-btn"
                        data-entry-id="{entry.pk}"
                        data-entry-title="{title}"
                        title="Delete entry">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
    </div>
    '''

    return JsonResponse({'html': html.strip(), 'entry_id': entry.pk})


def get_file_type(mime_type):
    """Determine file type from MIME type."""
    if mime_type in settings.ALLOWED_IMAGE_TYPES:
        return 'image'
    elif mime_type in settings.ALLOWED_AUDIO_TYPES:
        return 'audio'
    elif mime_type in settings.ALLOWED_VIDEO_TYPES:
        return 'video'
    return None


@login_required
@require_POST
def attachment_upload(request, entry_pk):
    """
    Handle file upload for an entry.
    Returns JSON with file info on success.
    """
    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']

    # Validate file size
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        return JsonResponse({'error': f'File too large. Maximum size is {max_mb}MB'}, status=400)

    # Validate file type
    mime_type = uploaded_file.content_type
    file_type = get_file_type(mime_type)

    if not file_type:
        return JsonResponse({'error': 'File type not allowed'}, status=400)

    # Create attachment
    attachment = Attachment.objects.create(
        entry=entry,
        file=uploaded_file,
        file_type=file_type,
        file_name=uploaded_file.name,
        file_size=uploaded_file.size,
        mime_type=mime_type,
    )

    return JsonResponse({
        'id': attachment.id,
        'url': attachment.file.url,
        'file_name': attachment.file_name,
        'file_type': attachment.file_type,
        'size_display': attachment.size_display,
        'mime_type': attachment.mime_type,
    })


@login_required
@require_POST
def attachment_delete(request, pk):
    """Delete an attachment."""
    attachment = get_object_or_404(Attachment, pk=pk, entry__user=request.user)

    # Delete the file from storage
    attachment.file.delete(save=False)
    attachment.delete()

    return JsonResponse({'success': True})


@login_required
def attachment_list(request, entry_pk):
    """Get list of attachments for an entry (JSON)."""
    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
    attachments = entry.attachments.all()

    data = [{
        'id': a.id,
        'url': a.file.url,
        'file_name': a.file_name,
        'file_type': a.file_type,
        'size_display': a.size_display,
        'mime_type': a.mime_type,
    } for a in attachments]

    return JsonResponse({'attachments': data})


@login_required
@require_POST
def upload_inline_image(request):
    """
    Upload an image for inline use in entry content.
    Returns JSON with the image URL for Markdown embedding.
    """
    import os
    import uuid
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']

    # Validate file size (10MB limit for inline images)
    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        return JsonResponse({'error': 'Image too large. Maximum size is 10MB'}, status=400)

    # Validate file type - images only
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if uploaded_file.content_type not in allowed_types:
        return JsonResponse({'error': 'Only images are allowed (jpg, png, gif, webp)'}, status=400)

    # Generate unique filename
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if not ext:
        ext = '.jpg'
    filename = f"{uuid.uuid4().hex}{ext}"

    # Save to user-specific folder
    path = f"journal/images/{request.user.id}/{filename}"
    saved_path = default_storage.save(path, ContentFile(uploaded_file.read()))

    # Get the URL
    url = default_storage.url(saved_path)

    return JsonResponse({
        'success': True,
        'url': url,
        'filename': filename,
    })


@login_required
@require_POST
def entry_quick_save(request):
    """
    Quick save endpoint for creating/updating entries via AJAX.
    Used when user drops files on a new entry - saves the entry first.
    """
    entry_pk = request.POST.get('entry_pk')
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '')
    entry_date_str = request.POST.get('entry_date', '')
    mood = request.POST.get('mood', '')
    energy = request.POST.get('energy', '')

    # Parse entry date
    try:
        entry_date = date.fromisoformat(entry_date_str) if entry_date_str else date.today()
    except ValueError:
        entry_date = date.today()

    if entry_pk:
        # Update existing entry
        entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
        entry.title = title or entry.title
        entry.content = content
        entry.entry_date = entry_date
        entry.mood = mood
        entry.energy = energy
        entry.is_analyzed = False  # Re-analyze on edit
        entry.save()
    else:
        # Create new entry
        entry = Entry.objects.create(
            user=request.user,
            title=title or 'Untitled',
            content=content,
            entry_date=entry_date,
            mood=mood,
            energy=energy,
        )

    return JsonResponse({
        'success': True,
        'entry_pk': entry.pk,
        'edit_url': f'/journal/{entry.pk}/edit/',
    })


@login_required
def import_entries(request):
    """Import journal entries from a file."""
    from .import_parser import parse_import_file

    context = get_sidebar_context(request.user)
    context['imported_count'] = 0
    context['skipped_count'] = 0
    context['errors'] = []
    context['preview_entries'] = []
    context['show_results'] = False

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')

        # Handle import action - uses session data, no file needed
        if action == 'import':
            pending = request.session.get('pending_import', [])
            if not pending:
                messages.error(request, 'No pending import found. Please upload your file again.')
                return render(request, 'journal/import.html', context)

            skip_duplicates = request.POST.get('skip_duplicates') == 'on'

            # Build list of entries to create
            entries_to_create = []
            skipped = 0

            for entry_data in pending:
                entry_date = date.fromisoformat(entry_data['entry_date'])

                # Check for duplicates
                if skip_duplicates:
                    existing = Entry.objects.filter(
                        user=request.user,
                        entry_date=entry_date,
                        title=entry_data['title']
                    ).exists()
                    if existing:
                        skipped += 1
                        continue

                # Add location to content if present
                content = entry_data['content']
                if entry_data.get('location'):
                    content += f"\n\n*Location: {entry_data['location']}*"

                entries_to_create.append(Entry(
                    user=request.user,
                    entry_date=entry_date,
                    title=entry_data['title'],
                    content=content,
                    word_count=len(content.split()) if content else 0,
                    is_analyzed=False,  # Will be analyzed later
                ))

            # Bulk create entries (doesn't trigger signals - much faster!)
            if entries_to_create:
                try:
                    Entry.objects.bulk_create(entries_to_create, batch_size=100)
                    imported = len(entries_to_create)
                except Exception as e:
                    context['errors'].append(f"Bulk import error: {str(e)}")
                    imported = 0
            else:
                imported = 0

            # Clear session data
            if 'pending_import' in request.session:
                del request.session['pending_import']

            context['imported_count'] = imported
            context['skipped_count'] = skipped
            context['show_results'] = True

            if imported > 0:
                messages.success(request, f'Successfully imported {imported} entries! Analysis skipped for speed - entries will be analyzed when you view them.')
            if skipped > 0:
                messages.info(request, f'Skipped {skipped} duplicate entries.')

            return render(request, 'journal/import.html', context)

        # Handle preview action - requires file upload
        if 'file' not in request.FILES:
            messages.error(request, 'Please select a file to import.')
            return render(request, 'journal/import.html', context)

        uploaded_file = request.FILES['file']

        # Validate file type
        if not uploaded_file.name.endswith(('.txt', '.md', '.markdown')):
            messages.error(request, 'Please upload a .txt or .md file.')
            return render(request, 'journal/import.html', context)

        # Read and decode the file
        try:
            content = uploaded_file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode('latin-1')
            except Exception:
                messages.error(request, 'Could not read file. Please ensure it is a text file.')
                return render(request, 'journal/import.html', context)

        # Get format hint from form
        format_hint = request.POST.get('format', 'auto')

        # Parse the entries
        try:
            parsed_entries = parse_import_file(content, format_hint)
        except Exception as e:
            messages.error(request, f'Error parsing file: {str(e)}')
            return render(request, 'journal/import.html', context)

        if not parsed_entries:
            messages.warning(request, 'No entries found in the file. Check the format.')
            return render(request, 'journal/import.html', context)

        # Show preview of entries to be imported
        context['preview_entries'] = parsed_entries[:20]  # Limit preview
        context['total_entries'] = len(parsed_entries)
        context['show_preview'] = True
        # Store parsed data in session for import
        request.session['pending_import'] = [
            {
                'entry_date': e.entry_date.isoformat(),
                'title': e.title,
                'content': e.content,
                'tags': e.tags,
                'location': e.location,
            }
            for e in parsed_entries
        ]
        messages.info(request, f'Found {len(parsed_entries)} entries. Review and click Import to proceed.')

    return render(request, 'journal/import.html', context)


# =============================================================================
# Slash Commands API
# =============================================================================

SLASH_COMMANDS = [
    {
        'command': '/book',
        'name': 'Book',
        'icon': 'bi-book',
        'description': 'Log a book you\'re reading',
        'fields': [
            {'name': 'title', 'label': 'Title', 'type': 'text', 'required': True},
            {'name': 'author', 'label': 'Author', 'type': 'text', 'required': False},
            {'name': 'status', 'label': 'Status', 'type': 'select', 'required': False,
             'options': [('reading', 'Reading'), ('finished', 'Finished'), ('abandoned', 'Abandoned')]},
            {'name': 'page', 'label': 'Page/Chapter', 'type': 'number', 'required': False},
            {'name': 'rating', 'label': 'Rating', 'type': 'rating', 'required': False},
        ],
    },
    {
        'command': '/watched',
        'name': 'Watched',
        'icon': 'bi-film',
        'description': 'Log a movie or show',
        'fields': [
            {'name': 'title', 'label': 'Title', 'type': 'text', 'required': True},
            {'name': 'type', 'label': 'Type', 'type': 'select', 'required': False,
             'options': [('movie', 'Movie'), ('show', 'TV Show'), ('documentary', 'Documentary')]},
            {'name': 'rating', 'label': 'Rating', 'type': 'rating', 'required': False},
        ],
    },
    {
        'command': '/travel',
        'name': 'Travel',
        'icon': 'bi-geo-alt',
        'description': 'Log a trip or journey',
        'fields': [
            {'name': 'mode', 'label': 'Mode', 'type': 'select', 'required': True,
             'options': [('car', 'Car'), ('plane', 'Plane'), ('train', 'Train'),
                        ('bus', 'Bus'), ('walk', 'Walk'), ('bike', 'Bike'), ('boat', 'Boat')]},
            {'name': 'origin', 'label': 'From', 'type': 'text', 'required': True},
            {'name': 'destination', 'label': 'To', 'type': 'text', 'required': True},
        ],
    },
    {
        'command': '/workout',
        'name': 'Workout',
        'icon': 'bi-heart-pulse',
        'description': 'Log exercise',
        'fields': [
            {'name': 'type', 'label': 'Type', 'type': 'select', 'required': True,
             'options': [('run', 'Running'), ('walk', 'Walking'), ('gym', 'Gym'),
                        ('yoga', 'Yoga'), ('swim', 'Swimming'), ('bike', 'Cycling'),
                        ('hike', 'Hiking'), ('sports', 'Sports'), ('other', 'Other')]},
            {'name': 'duration', 'label': 'Duration (min)', 'type': 'number', 'required': False},
            {'name': 'intensity', 'label': 'Intensity', 'type': 'select', 'required': False,
             'options': [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]},
        ],
    },
    {
        'command': '/person',
        'name': 'Person',
        'icon': 'bi-person',
        'description': 'Log who you spent time with',
        'fields': [
            {'name': 'name', 'label': 'Name', 'type': 'text', 'required': True},
            {'name': 'context', 'label': 'Context', 'type': 'text', 'required': False,
             'placeholder': 'e.g., lunch, meeting, call'},
        ],
    },
    {
        'command': '/place',
        'name': 'Place',
        'icon': 'bi-pin-map',
        'description': 'Log where you are',
        'fields': [
            {'name': 'name', 'label': 'Name', 'type': 'text', 'required': True},
            {'name': 'type', 'label': 'Type', 'type': 'select', 'required': False,
             'options': [('restaurant', 'Restaurant'), ('cafe', 'Cafe'), ('bar', 'Bar'),
                        ('park', 'Park'), ('office', 'Office'), ('home', 'Home'),
                        ('store', 'Store'), ('gym', 'Gym'), ('other', 'Other')]},
        ],
    },
    {
        'command': '/meal',
        'name': 'Meal',
        'icon': 'bi-cup-hot',
        'description': 'Log what you ate',
        'fields': [
            {'name': 'meal', 'label': 'Meal', 'type': 'select', 'required': True,
             'options': [('breakfast', 'Breakfast'), ('lunch', 'Lunch'),
                        ('dinner', 'Dinner'), ('snack', 'Snack')]},
            {'name': 'what', 'label': 'What', 'type': 'text', 'required': True,
             'placeholder': 'What did you eat?'},
        ],
    },
    {
        'command': '/dream',
        'name': 'Dream',
        'icon': 'bi-cloud-moon',
        'description': 'Flag as dream journal',
        'fields': [],
    },
    {
        'command': '/gratitude',
        'name': 'Gratitude',
        'icon': 'bi-heart',
        'description': 'Log things you\'re grateful for',
        'fields': [
            {'name': 'item1', 'label': 'Grateful for...', 'type': 'text', 'required': True},
            {'name': 'item2', 'label': 'Also grateful for...', 'type': 'text', 'required': False},
            {'name': 'item3', 'label': 'And grateful for...', 'type': 'text', 'required': False},
        ],
    },
    {
        'command': '/goal',
        'name': 'Goal',
        'icon': 'bi-bullseye',
        'description': 'Link to a goal',
        'fields': [],
        'special': 'goal_picker',
    },
    {
        'command': '/habit',
        'name': 'Habit',
        'icon': 'bi-repeat',
        'description': 'Link to a habit',
        'fields': [],
        'special': 'habit_picker',
    },
    {
        'command': '/pain',
        'name': 'Pain Log',
        'icon': 'bi-bandaid',
        'description': 'Track pain or discomfort',
        'special': 'capture_form',
        'captureType': 'pain',
        'fields': [
            {'name': 'location', 'label': 'Location', 'type': 'select', 'required': True,
             'options': [('head', 'Head'), ('neck', 'Neck'), ('back', 'Back'), ('chest', 'Chest'),
                        ('arm', 'Arm'), ('leg', 'Leg'), ('tooth', 'Tooth'), ('stomach', 'Stomach'),
                        ('joint', 'Joint'), ('other', 'Other')]},
            {'name': 'time', 'label': 'Time (optional)', 'type': 'time', 'required': False,
             'placeholder': 'Leave blank for now'},
            {'name': 'intensity', 'label': 'Intensity (1-10)', 'type': 'range', 'required': True,
             'min': 1, 'max': 10, 'default': 5},
            {'name': 'pain_type', 'label': 'Type', 'type': 'select', 'required': False,
             'options': [('', '-- Select --'), ('sharp', 'Sharp'), ('dull', 'Dull'),
                        ('throbbing', 'Throbbing'), ('burning', 'Burning'),
                        ('aching', 'Aching'), ('stabbing', 'Stabbing')]},
            {'name': 'duration', 'label': 'Duration', 'type': 'select', 'required': False,
             'options': [('', '-- Select --'), ('brief', 'Brief (minutes)'), ('hours', 'Hours'),
                        ('all_day', 'All Day'), ('ongoing', 'Ongoing')]},
        ],
    },
    {
        'command': '/clover',
        'name': 'Clover',
        'icon': '🍀',
        'description': 'Log a special moment',
        'is_emoji_icon': True,
        'special': 'capture_form',
        'captureType': 'intimacy',
        'fields': [
            {'name': 'rating', 'label': 'Rating (optional)', 'type': 'rating', 'required': False},
            {'name': 'notes', 'label': 'Notes (optional)', 'type': 'textarea', 'required': False, 'placeholder': 'Any notes...'},
        ],
    },
    {
        'command': '/cycle',
        'name': 'Cycle',
        'icon': 'bi-calendar-heart',
        'description': 'Track cycle or symptoms',
        'special': 'capture_form',
        'captureType': 'cycle',
        'fields': [
            {'name': 'event_type', 'label': 'Event', 'type': 'select', 'required': True,
             'options': [('period_start', 'Period Started'), ('period_end', 'Period Ended'),
                        ('symptom', 'Symptom Only'), ('note', 'Note')]},
            {'name': 'flow_level', 'label': 'Flow (if applicable)', 'type': 'select', 'required': False,
             'options': [('', '-- Select --'), ('light', 'Light'), ('medium', 'Medium'), ('heavy', 'Heavy')]},
        ],
    },
]


@login_required
def get_slash_commands(request):
    """Return all available slash commands, filtered by user settings."""
    commands = list(SLASH_COMMANDS)  # Create a copy

    # Filter wellness commands based on user profile settings
    profile = request.user.profile

    # Remove /clover if intimacy tracking is disabled
    if not profile.enable_intimacy_tracking:
        commands = [cmd for cmd in commands if cmd['command'] != '/clover']

    # Remove /cycle if cycle tracking is disabled
    if not profile.enable_cycle_tracking:
        commands = [cmd for cmd in commands if cmd['command'] != '/cycle']

    return JsonResponse({'commands': commands})


@login_required
@require_POST
def save_capture(request):
    """Save a capture from a slash command."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    entry_pk = data.get('entry_pk')
    capture_type = data.get('capture_type')
    capture_data = data.get('data', {})

    if not entry_pk:
        return JsonResponse({'error': 'Entry PK required'}, status=400)

    if not capture_type:
        return JsonResponse({'error': 'Capture type required'}, status=400)

    # Validate capture type
    valid_types = [c[0] for c in EntryCapture.CAPTURE_TYPES]
    if capture_type not in valid_types:
        return JsonResponse({'error': f'Invalid capture type: {capture_type}'}, status=400)

    # Get the entry (must belong to user)
    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)

    # Handle gratitude items specially
    if capture_type == 'gratitude':
        items = []
        for key in ['item1', 'item2', 'item3']:
            if capture_data.get(key):
                items.append(capture_data[key])
        capture_data = {'items': items}

    # Convert numeric fields from strings to integers
    if capture_type == 'watched' and capture_data.get('rating'):
        try:
            capture_data['rating'] = int(capture_data['rating'])
        except (ValueError, TypeError):
            capture_data['rating'] = 0

    if capture_type == 'workout' and capture_data.get('duration'):
        try:
            capture_data['duration'] = int(capture_data['duration'])
        except (ValueError, TypeError):
            capture_data['duration'] = 0

    # Handle wellness captures - also create corresponding wellness models
    try:
        if capture_type == 'pain':
            from apps.wellness.models import PainLog
            from datetime import datetime, time as dt_time
            try:
                capture_data['intensity'] = int(capture_data.get('intensity', 5))
            except (ValueError, TypeError):
                capture_data['intensity'] = 5
            # Use user-provided time or default to current time
            user_time = capture_data.get('time')
            if user_time:
                try:
                    # Parse time string (HH:MM format)
                    hours, minutes = map(int, user_time.split(':'))
                    pain_time = dt_time(hours, minutes)
                except (ValueError, TypeError):
                    pain_time = datetime.now().time()
            else:
                pain_time = datetime.now().time()
            # Convert date to datetime for logged_at field
            logged_datetime = datetime.combine(entry.entry_date, pain_time)
            logged_datetime = timezone.make_aware(logged_datetime) if timezone.is_naive(logged_datetime) else logged_datetime
            PainLog.objects.create(
                user=request.user,
                entry=entry,
                logged_at=logged_datetime,
                location=capture_data.get('location', 'other'),
                intensity=capture_data['intensity'],
                pain_type=capture_data.get('pain_type', ''),
                duration=capture_data.get('duration', ''),
            )

        elif capture_type == 'intimacy':
            from apps.wellness.models import IntimacyLog
            from datetime import datetime
            from django.utils import timezone
            rating = capture_data.get('rating')
            if rating:
                try:
                    rating = int(rating)
                except (ValueError, TypeError):
                    rating = None
            # Use entry date for logged_at, not current time
            logged_datetime = datetime.combine(entry.entry_date, datetime.now().time())
            logged_datetime = timezone.make_aware(logged_datetime) if timezone.is_naive(logged_datetime) else logged_datetime
            IntimacyLog.objects.create(
                user=request.user,
                entry=entry,
                logged_at=logged_datetime,
                rating=rating,
                notes=capture_data.get('notes', ''),
            )

        elif capture_type == 'cycle':
            from apps.wellness.models import CycleLog
            CycleLog.objects.create(
                user=request.user,
                entry=entry,
                log_date=entry.entry_date,
                event_type=capture_data.get('event_type', 'note'),
                flow_level=capture_data.get('flow_level', ''),
                symptoms=capture_data.get('symptoms', []),
                notes=capture_data.get('notes', ''),
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error creating wellness log for {capture_type}: {e}")
        return JsonResponse({'error': f'Failed to create wellness log: {str(e)}'}, status=500)

    # Create the capture
    capture = EntryCapture.objects.create(
        entry=entry,
        capture_type=capture_type,
        data=capture_data,
    )

    return JsonResponse({
        'success': True,
        'capture': {
            'id': capture.id,
            'type': capture.capture_type,
            'icon': capture.icon,
            'display_text': capture.display_text,
        }
    })


@login_required
@require_POST
def delete_capture(request, pk):
    """Delete a capture."""
    capture = get_object_or_404(EntryCapture, pk=pk, entry__user=request.user)
    capture.delete()
    return JsonResponse({'success': True})


@login_required
def get_entry_captures(request, entry_pk):
    """Get all captures for an entry."""
    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
    captures = entry.captures.all()

    data = [{
        'id': c.id,
        'type': c.capture_type,
        'icon': c.icon,
        'display_text': c.display_text,
        'data': c.data,
    } for c in captures]

    return JsonResponse({'captures': data})


@login_required
def capture_count(request):
    """Get the count of visits/uses for a specific capture type and name."""
    capture_type = request.GET.get('type', '')
    name = request.GET.get('name', '')

    if not capture_type or not name:
        return JsonResponse({'count': 0})

    # Build the query based on capture type
    from django.db.models import Q

    if capture_type == 'place':
        # For places, match by name
        count = EntryCapture.objects.filter(
            entry__user=request.user,
            capture_type='place',
            data__name__iexact=name
        ).count()
    elif capture_type == 'travel':
        # For travel, match by destination
        count = EntryCapture.objects.filter(
            entry__user=request.user,
            capture_type='travel',
            data__destination__iexact=name
        ).count()
    elif capture_type == 'watched':
        # For watched, match by title
        count = EntryCapture.objects.filter(
            entry__user=request.user,
            capture_type='watched',
            data__title__iexact=name
        ).count()
    elif capture_type == 'person':
        # For person, match by name
        count = EntryCapture.objects.filter(
            entry__user=request.user,
            capture_type='person',
            data__name__iexact=name
        ).count()
    else:
        count = 0

    return JsonResponse({'count': count, 'type': capture_type, 'name': name})


@login_required
def goals_search(request):
    """Search user's goals for /goal command."""
    from apps.goals.models import Goal

    query = request.GET.get('q', '').strip()
    # Filter for active goals (not completed or abandoned)
    goals = Goal.objects.filter(
        user=request.user,
        status__in=['not_started', 'in_progress', 'on_hold']
    ).prefetch_related('milestones', 'linked_habits')

    if query:
        goals = goals.filter(title__icontains=query)

    goals = goals[:10]

    # Map priority to colors
    priority_colors = {
        'low': '#6b7280',
        'medium': '#f59e0b',
        'high': '#ef4444',
    }

    data = []
    for g in goals:
        # Get incomplete milestones (tasks)
        tasks = [{
            'id': m.id,
            'title': m.title,
            'is_completed': m.is_completed,
        } for m in g.milestones.filter(is_completed=False)[:5]]

        # Get linked habits
        habits = [{
            'id': h.id,
            'name': h.name,
            'icon': h.icon,
        } for h in g.linked_habits.filter(is_active=True)[:3]]

        data.append({
            'id': g.id,
            'title': g.title,
            'icon': g.category_icon,
            'color': priority_colors.get(g.priority, '#4f46e5'),
            'progress': g.progress_percentage,
            'tasks': tasks,
            'habits': habits,
        })

    return JsonResponse({'goals': data})


@login_required
def habits_search(request):
    """Search user's habits for /habit command."""
    from apps.habits.models import Habit

    query = request.GET.get('q', '').strip()
    habits = Habit.objects.filter(user=request.user, is_active=True)

    if query:
        habits = habits.filter(name__icontains=query)

    habits = habits[:10]

    data = [{
        'id': h.id,
        'name': h.name,
        'icon': h.icon,
        'color': h.color,
        'current_streak': h.current_streak,
    } for h in habits]

    return JsonResponse({'habits': data})


@login_required
def habits_detect(request):
    """Detect habit mentions in content and suggest linking them."""
    from apps.habits.models import Habit
    import re

    content = request.GET.get('content', '').strip().lower()
    if not content:
        return JsonResponse({'detected_habits': []})

    # Get user's active habits
    user_habits = Habit.objects.filter(user=request.user, is_active=True)

    detected = []
    for habit in user_habits:
        # Check if habit name appears in content (case-insensitive)
        habit_name_lower = habit.name.lower()
        # Use word boundaries to avoid false matches
        pattern = r'\b' + re.escape(habit_name_lower) + r'\b'

        if re.search(pattern, content):
            detected.append({
                'id': habit.id,
                'name': habit.name,
                'icon': habit.icon,
                'color': habit.color,
                'frequency': habit.frequency_display,
            })

    return JsonResponse({'detected_habits': detected})


# =============================================================================
# Quick Picker API Endpoints (for simplified slash commands)
# =============================================================================

@login_required
def people_search(request):
    """Search/list people for /person quick picker."""
    from apps.analytics.models import TrackedPerson

    query = request.GET.get('q', '').strip()
    people = TrackedPerson.objects.filter(user=request.user).order_by('-mention_count')

    if query:
        people = people.filter(name__icontains=query)

    people = people[:15]

    data = [{
        'id': p.id,
        'name': p.name,
        'relationship': p.get_relationship_display(),
        'mention_count': p.mention_count,
    } for p in people]

    return JsonResponse({'items': data})


@login_required
@require_POST
def people_create(request):
    """Create a new person for /person quick picker."""
    from apps.analytics.models import TrackedPerson

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    entry_id = data.get('entry_id')

    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)

    # Check if person already exists
    existing = TrackedPerson.objects.filter(
        user=request.user,
        normalized_name=name.lower()
    ).first()

    if existing:
        person = existing
        created = False
    else:
        # Create new person
        person = TrackedPerson.objects.create(
            user=request.user,
            name=name,
            normalized_name=name.lower()
        )
        created = True

    # Update mention stats if entry_id provided
    if entry_id:
        try:
            entry = Entry.objects.get(pk=entry_id, user=request.user)
            _update_person_mention(person, entry)
        except Entry.DoesNotExist:
            pass

    return JsonResponse({
        'id': person.id,
        'name': person.name,
        'created': created
    })


@login_required
@require_POST
def people_mention(request):
    """Record a person mention from quick picker (for existing people)."""
    from apps.analytics.models import TrackedPerson

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    person_id = data.get('person_id')
    entry_id = data.get('entry_id')

    if not person_id:
        return JsonResponse({'error': 'person_id is required'}, status=400)

    try:
        person = TrackedPerson.objects.get(pk=person_id, user=request.user)
    except TrackedPerson.DoesNotExist:
        return JsonResponse({'error': 'Person not found'}, status=404)

    if entry_id:
        try:
            entry = Entry.objects.get(pk=entry_id, user=request.user)
            _update_person_mention(person, entry)
        except Entry.DoesNotExist:
            pass

    return JsonResponse({'success': True})


def _update_person_mention(person, entry):
    """Update mention stats for a person."""
    person.mention_count += 1
    entry_date = entry.entry_date

    if not person.first_mention_date or entry_date < person.first_mention_date:
        person.first_mention_date = entry_date
    if not person.last_mention_date or entry_date > person.last_mention_date:
        person.last_mention_date = entry_date

    person.save()


@login_required
def books_search(request):
    """Search/list books for /book quick picker."""
    from apps.analytics.models import TrackedBook

    query = request.GET.get('q', '').strip()
    books = TrackedBook.objects.filter(user=request.user).order_by('-last_entry_date')

    if query:
        books = books.filter(title__icontains=query)

    books = books[:15]

    data = [{
        'id': b.id,
        'name': b.title,
        'author': b.author or '',
        'status': b.get_status_display(),
    } for b in books]

    return JsonResponse({'items': data})


@login_required
@require_POST
def books_create(request):
    """Create a new book for /book quick picker."""
    from apps.analytics.models import TrackedBook

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    title = data.get('name', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    # Check if book already exists
    existing = TrackedBook.objects.filter(
        user=request.user,
        normalized_title=title.lower()
    ).first()

    if existing:
        return JsonResponse({
            'id': existing.id,
            'name': existing.title,
            'created': False
        })

    # Create new book
    book = TrackedBook.objects.create(
        user=request.user,
        title=title,
        normalized_title=title.lower(),
        status='reading'
    )

    return JsonResponse({
        'id': book.id,
        'name': book.title,
        'created': True
    })


@login_required
@require_POST
def link_goal(request):
    """Link a journal entry to a goal."""
    from apps.goals.models import Goal

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    entry_pk = data.get('entry_pk')
    goal_id = data.get('goal_id')

    if not entry_pk or not goal_id:
        return JsonResponse({'error': 'Entry PK and Goal ID required'}, status=400)

    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
    goal = get_object_or_404(Goal, pk=goal_id, user=request.user)

    # Add entry to goal's journal_entries
    goal.journal_entries.add(entry)

    return JsonResponse({
        'success': True,
        'goal': {
            'id': goal.id,
            'title': goal.title,
        }
    })


@login_required
@require_POST
def link_habit(request):
    """Link a journal entry to a habit and optionally create a check-in."""
    from apps.habits.models import Habit, HabitCheckin
    from django.utils import timezone

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    entry_pk = data.get('entry_pk')
    habit_id = data.get('habit_id')
    create_checkin = data.get('create_checkin', True)

    if not entry_pk or not habit_id:
        return JsonResponse({'error': 'Entry PK and Habit ID required'}, status=400)

    entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
    habit = get_object_or_404(Habit, pk=habit_id, user=request.user)

    # Add entry to habit's journal_entries
    habit.journal_entries.add(entry)

    # Optionally create a check-in for today
    checkin_created = False
    if create_checkin:
        today = timezone.now().date()
        checkin, created = HabitCheckin.objects.get_or_create(
            habit=habit,
            check_date=today,
            defaults={
                'completed': True,
                'journal_entry': entry,
            }
        )
        if created:
            checkin_created = True
        elif not checkin.journal_entry:
            # Update existing checkin to link to this entry
            checkin.journal_entry = entry
            checkin.save()

    return JsonResponse({
        'success': True,
        'habit': {
            'id': habit.id,
            'name': habit.name,
        },
        'checkin_created': checkin_created,
    })


@login_required
@require_POST
def complete_task(request):
    """Complete a task/milestone within a goal."""
    from apps.goals.models import Milestone
    from django.utils import timezone

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    task_id = data.get('task_id')
    entry_pk = data.get('entry_pk')

    if not task_id:
        return JsonResponse({'error': 'Task ID required'}, status=400)

    # Get the milestone (task) - verify it belongs to user's goal
    milestone = get_object_or_404(Milestone, pk=task_id, goal__user=request.user)

    # Mark as completed
    milestone.is_completed = True
    milestone.completed_at = timezone.now()
    milestone.save()

    # If entry provided, link it to the goal
    if entry_pk:
        entry = get_object_or_404(Entry, pk=entry_pk, user=request.user)
        milestone.goal.journal_entries.add(entry)

    return JsonResponse({
        'success': True,
        'task': {
            'id': milestone.id,
            'title': milestone.title,
            'goal_id': milestone.goal.id,
            'goal_title': milestone.goal.title,
        }
    })


@login_required
@require_POST
def analyze_entries(request):
    """
    Analyze unanalyzed entries for the current user.
    Called via AJAX to trigger analysis after import.
    """
    from .signals import run_sync_analysis

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    limit = data.get('limit', 50)  # Default to 50 entries per batch

    # Get unanalyzed entries for this user
    entries = Entry.objects.filter(
        user=request.user,
        is_analyzed=False
    ).order_by('entry_date')[:limit]

    total_unanalyzed = Entry.objects.filter(
        user=request.user,
        is_analyzed=False
    ).count()

    analyzed = 0
    errors = 0

    for entry in entries:
        try:
            run_sync_analysis(entry)
            analyzed += 1
        except Exception as e:
            errors += 1
            # Log but continue
            import logging
            logging.getLogger(__name__).error(f"Error analyzing entry {entry.id}: {e}")

    remaining = total_unanalyzed - analyzed

    return JsonResponse({
        'success': True,
        'analyzed': analyzed,
        'errors': errors,
        'remaining': remaining,
        'total_unanalyzed': total_unanalyzed,
    })


# =============================================================================
# Entry Modal API Views
# =============================================================================

@login_required
@require_http_methods(["GET"])
def entry_modal_detail(request, pk):
    """Get entry details for modal display."""
    from .templatetags.markdown_extras import render_markdown

    entry = get_object_or_404(Entry, pk=pk, user=request.user)

    # Render markdown to HTML
    content_html = render_markdown(entry.content)

    # Get analysis if available
    analysis_data = None
    if hasattr(entry, 'analysis') and entry.analysis:
        analysis_data = {
            'sentiment_score': entry.analysis.sentiment_score,
            'sentiment_label': entry.analysis.sentiment_label,
            'detected_mood': entry.analysis.detected_mood,
            'themes': entry.analysis.themes,
            'keywords': entry.analysis.keywords,
        }

    return JsonResponse({
        'id': entry.id,
        'title': entry.title or '',
        'content': entry.content,  # Raw content for editing
        'content_html': str(content_html),  # Rendered HTML for display
        'entry_date': entry.entry_date.isoformat(),
        'entry_date_display': entry.entry_date.strftime('%B %d, %Y'),
        'mood': entry.mood or '',
        'mood_emoji': entry.mood_emoji,
        'word_count': entry.word_count,
        'analysis': analysis_data,
        'edit_url': f'/journal/{entry.pk}/edit/',
        'detail_url': f'/journal/{entry.pk}/',
    })


@login_required
@require_http_methods(["POST"])
def entry_modal_update(request, pk):
    """Update entry content from modal."""
    entry = get_object_or_404(Entry, pk=pk, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    # Update fields
    if 'title' in data:
        entry.title = data['title']
    if 'content' in data:
        entry.content = data['content']
        entry.word_count = len(data['content'].split())
    if 'mood' in data:
        entry.mood = data['mood']

    entry.save()

    # Re-analyze the entry after update
    from .signals import run_sync_analysis
    try:
        run_sync_analysis(entry)
    except Exception:
        pass  # Analysis failure shouldn't block the save

    return JsonResponse({
        'success': True,
        'id': entry.id,
        'word_count': entry.word_count,
    })


# =============================================================================
# POV Sharing Views
# =============================================================================

@login_required
def shared_povs_list(request):
    """List all POVs shared with the current user."""
    from .models import SharedPOV
    from .services.pov import get_shared_povs_for_user, get_unread_pov_count

    received_povs = get_shared_povs_for_user(request.user)

    # Pagination
    paginator = Paginator(received_povs, 20)
    page = request.GET.get('page', 1)
    povs = paginator.get_page(page)

    # Count unread
    unread_count = get_unread_pov_count(request.user)

    return render(request, 'journal/shared/pov_list.html', {
        'povs': povs,
        'unread_count': unread_count,
    })


@login_required
def shared_pov_detail(request, pk):
    """View a specific shared POV and its replies."""
    from .models import SharedPOV
    from .services.pov import can_view_pov, can_reply_to_pov, mark_pov_as_read

    pov = get_object_or_404(SharedPOV, pk=pk)

    # Check permission
    if not can_view_pov(pov, request.user):
        messages.error(request, "You don't have permission to view this.")
        return redirect('journal:shared_povs_list')

    # Mark as read if recipient
    if request.user != pov.author:
        mark_pov_as_read(pk, request.user)

    # Get replies
    replies = pov.replies.select_related('author', 'author__profile')

    # Get all recipients for display
    recipients = pov.recipients.select_related('user', 'user__profile')

    return render(request, 'journal/shared/pov_detail.html', {
        'pov': pov,
        'replies': replies,
        'recipients': recipients,
        'can_reply': can_reply_to_pov(pov, request.user),
    })


@login_required
def pov_view_and_redirect(request, pk):
    """Mark a POV as read and redirect to the journal entry."""
    from .models import SharedPOV
    from .services.pov import mark_pov_as_read

    pov = get_object_or_404(SharedPOV, pk=pk)

    # Mark as read
    mark_pov_as_read(pk, request.user)

    # Redirect to the entry for that date
    return redirect(f"{reverse('journal:entry_list')}?date={pov.entry.entry_date.strftime('%Y-%m-%d')}")


@login_required
@require_POST
def pov_reply_create(request, pov_id):
    """Create a reply to a POV."""
    from .models import SharedPOV
    from .services.pov import can_reply_to_pov, create_pov_reply

    pov = get_object_or_404(SharedPOV, pk=pov_id)

    if not can_reply_to_pov(pov, request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Reply cannot be empty'}, status=400)

    if len(content) > 2000:
        return JsonResponse({'error': 'Reply too long (max 2000 chars)'}, status=400)

    try:
        reply = create_pov_reply(pov, request.user, content)

        return JsonResponse({
            'success': True,
            'reply': {
                'id': reply.id,
                'author': reply.author.profile.display_name,
                'content': reply.content,
                'created_at': reply.created_at.isoformat(),
            }
        })
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)


@login_required
def unread_povs_count(request):
    """AJAX endpoint to get unread POV count for nav badge."""
    from .services.pov import get_unread_pov_count

    count = get_unread_pov_count(request.user)
    return JsonResponse({'count': count})


@login_required
@require_POST
def pov_delete_recipient(request, pov_id):
    """Delete a POV for the recipient (removes from their journal)."""
    from .services.pov import delete_pov_for_recipient

    success = delete_pov_for_recipient(pov_id, request.user)

    if success:
        messages.success(request, "POV removed from your journal.")
    else:
        messages.error(request, "Could not delete POV. You may not be a recipient.")

    return redirect('journal:shared_povs_list')
