from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime

from apps.accounts.decorators import premium_required
from .models import Habit, HabitCheckin
from .forms import HabitForm


@login_required
def habit_list(request):
    """Display list of user's habits with today's status."""
    is_premium = request.user.profile.is_premium
    today = timezone.now().date()

    if is_premium:
        habits = Habit.objects.filter(user=request.user)

        # Filter by category or active status
        category = request.GET.get('category')
        show_archived = request.GET.get('archived') == '1'

        if category:
            habits = habits.filter(category=category)

        if not show_archived:
            habits = habits.filter(is_active=True)

        # Add today's status to each habit
        habits_with_status = []
        for habit in habits:
            habits_with_status.append({
                'habit': habit,
                'is_due_today': habit.is_due_on_date(today),
                'completed_today': habit.is_completed_on_date(today),
                'completion_rate': habit.get_completion_rate(30),
            })

        # Stats
        active_habits = Habit.objects.filter(user=request.user, is_active=True)
        due_today = sum(1 for h in active_habits if h.is_due_on_date(today))
        completed_today = sum(1 for h in active_habits if h.is_completed_on_date(today))

        stats = {
            'total': active_habits.count(),
            'due_today': due_today,
            'completed_today': completed_today,
            'completion_rate': (completed_today / due_today * 100) if due_today > 0 else 100,
        }
    else:
        # Free user - empty data
        habits_with_status = []
        category = None
        show_archived = False
        stats = {
            'total': 0,
            'due_today': 0,
            'completed_today': 0,
            'completion_rate': 0,
        }

    context = {
        'habits_with_status': habits_with_status,
        'category_choices': Habit.CATEGORY_CHOICES,
        'current_category': request.GET.get('category'),
        'show_archived': request.GET.get('archived') == '1',
        'today': today,
        'stats': stats,
        'active_page': 'habits',
        'current_year': today.year,
        'is_premium': is_premium,
    }
    return render(request, 'habits/habit_list.html', context)


@login_required
@premium_required
def habit_detail(request, pk):
    """Display a single habit with stats and history."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    today = timezone.now().date()

    # Get checkins for last 30 days for calendar view
    start_date = today - timedelta(days=29)
    checkins = habit.checkins.filter(
        check_date__gte=start_date,
        check_date__lte=today
    )
    checkin_dates = {c.check_date: c.completed for c in checkins}

    # Build calendar data
    calendar_data = []
    for i in range(30):
        date = start_date + timedelta(days=i)
        is_due = habit.is_due_on_date(date)
        completed = checkin_dates.get(date, False)
        calendar_data.append({
            'date': date,
            'is_due': is_due,
            'completed': completed,
            'is_today': date == today,
        })

    # Recent checkins with notes
    recent_checkins = habit.checkins.filter(note__isnull=False).exclude(note='')[:10]

    # Linked journal entries
    linked_entries = habit.journal_entries.all()[:5]

    context = {
        'habit': habit,
        'today': today,
        'is_due_today': habit.is_due_on_date(today),
        'completed_today': habit.is_completed_on_date(today),
        'calendar_data': calendar_data,
        'recent_checkins': recent_checkins,
        'linked_entries': linked_entries,
        'completion_rate_30': habit.get_completion_rate(30),
        'completion_rate_7': habit.get_completion_rate(7),
        'active_page': 'habits',
        'current_year': today.year,
    }
    return render(request, 'habits/habit_detail.html', context)


@login_required
@premium_required
def habit_create(request):
    """Create a new habit."""
    if request.method == 'POST':
        form = HabitForm(request.POST)
        if form.is_valid():
            habit = form.save(commit=False)
            habit.user = request.user
            habit.save()
            messages.success(request, f'Habit "{habit.name}" created!')
            return redirect('habits:habit_detail', pk=habit.pk)
    else:
        form = HabitForm()

    today = timezone.now().date()
    context = {
        'form': form,
        'is_edit': False,
        'active_page': 'habits',
        'current_year': today.year,
    }
    return render(request, 'habits/habit_form.html', context)


@login_required
@premium_required
def habit_edit(request, pk):
    """Edit an existing habit."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)

    if request.method == 'POST':
        form = HabitForm(request.POST, instance=habit)
        if form.is_valid():
            form.save()
            messages.success(request, f'Habit "{habit.name}" updated!')
            return redirect('habits:habit_detail', pk=habit.pk)
    else:
        form = HabitForm(instance=habit)

    today = timezone.now().date()
    context = {
        'form': form,
        'habit': habit,
        'is_edit': True,
        'active_page': 'habits',
        'current_year': today.year,
    }
    return render(request, 'habits/habit_form.html', context)


@login_required
@premium_required
def habit_delete(request, pk):
    """Delete a habit."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)

    if request.method == 'POST':
        name = habit.name
        habit.delete()
        messages.success(request, f'Habit "{name}" deleted.')
        return redirect('habits:habit_list')

    today = timezone.now().date()
    context = {
        'habit': habit,
        'active_page': 'habits',
        'current_year': today.year,
    }
    return render(request, 'habits/habit_confirm_delete.html', context)


@login_required
@premium_required
@require_POST
def habit_checkin(request, pk):
    """Toggle check-in for today."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    today = timezone.now().date()

    checkin, created = HabitCheckin.objects.get_or_create(
        habit=habit,
        check_date=today,
        defaults={'completed': True}
    )

    if not created:
        # Toggle completion status
        checkin.completed = not checkin.completed
        checkin.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'completed': checkin.completed,
            'current_streak': habit.current_streak,
            'total_completions': habit.total_completions,
        })

    return redirect('habits:habit_list')


@login_required
@premium_required
@require_POST
def habit_checkin_date(request, pk, date_str):
    """Check-in for a specific date."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)

    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date'}, status=400)

    note = request.POST.get('note', '')

    checkin, created = HabitCheckin.objects.get_or_create(
        habit=habit,
        check_date=check_date,
        defaults={'completed': True, 'note': note}
    )

    if not created:
        checkin.completed = not checkin.completed
        if note:
            checkin.note = note
        checkin.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'completed': checkin.completed,
            'current_streak': habit.current_streak,
        })

    return redirect('habits:habit_detail', pk=habit.pk)


@login_required
@premium_required
def habit_calendar(request, pk):
    """Calendar/heatmap view for a habit."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    today = timezone.now().date()

    # Get year and month from query params
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # Calculate start and end of month
    from calendar import monthrange
    first_day = datetime(year, month, 1).date()
    _, last_day_num = monthrange(year, month)
    last_day = datetime(year, month, last_day_num).date()

    # Get checkins for the month
    checkins = habit.checkins.filter(
        check_date__gte=first_day,
        check_date__lte=last_day
    )
    checkin_dates = {c.check_date: c.completed for c in checkins}

    # Build calendar data
    calendar_data = []
    current_date = first_day
    while current_date <= last_day:
        is_due = habit.is_due_on_date(current_date)
        completed = checkin_dates.get(current_date, False)
        calendar_data.append({
            'date': current_date,
            'day': current_date.day,
            'is_due': is_due,
            'completed': completed,
            'is_today': current_date == today,
            'is_future': current_date > today,
        })
        current_date += timedelta(days=1)

    # Previous/next month navigation
    if month == 1:
        prev_month = {'year': year - 1, 'month': 12}
    else:
        prev_month = {'year': year, 'month': month - 1}

    if month == 12:
        next_month = {'year': year + 1, 'month': 1}
    else:
        next_month = {'year': year, 'month': month + 1}

    context = {
        'habit': habit,
        'calendar_data': calendar_data,
        'year': year,
        'month': month,
        'month_name': first_day.strftime('%B'),
        'prev_month': prev_month,
        'next_month': next_month,
        'first_day_weekday': first_day.weekday(),
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'habits/partials/_calendar_month.html', context)

    return render(request, 'habits/habit_calendar.html', context)


@login_required
@premium_required
@require_POST
def habit_link_entry(request, pk):
    """Link a journal entry to a habit."""
    from apps.journal.models import Entry

    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    entry_id = request.POST.get('entry_id')

    if entry_id:
        entry = get_object_or_404(Entry, pk=entry_id, user=request.user)
        habit.journal_entries.add(entry)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'entry_id': entry.pk,
                'entry_title': entry.title or f"Entry from {entry.entry_date}",
            })
        messages.success(request, 'Journal entry linked to habit.')

    return redirect('habits:habit_detail', pk=habit.pk)


@login_required
@premium_required
@require_POST
def habit_unlink_entry(request, pk):
    """Unlink a journal entry from a habit."""
    from apps.journal.models import Entry

    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    entry_id = request.POST.get('entry_id')

    if entry_id:
        entry = get_object_or_404(Entry, pk=entry_id, user=request.user)
        habit.journal_entries.remove(entry)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'Journal entry unlinked from habit.')

    return redirect('habits:habit_detail', pk=habit.pk)


@login_required
@premium_required
@require_GET
def habit_entries_search(request, pk):
    """AJAX search for journal entries to link."""
    from apps.journal.models import Entry
    from django.db.models import Q

    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    query = request.GET.get('q', '')

    entries = Entry.objects.filter(user=request.user)
    if query:
        entries = entries.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    # Exclude already linked entries
    linked_ids = habit.journal_entries.values_list('pk', flat=True)
    entries = entries.exclude(pk__in=linked_ids)[:10]

    results = [{
        'id': e.pk,
        'title': e.title or f"Entry from {e.entry_date}",
        'date': e.entry_date.isoformat(),
        'preview': e.preview[:100],
    } for e in entries]

    return JsonResponse({'entries': results})
