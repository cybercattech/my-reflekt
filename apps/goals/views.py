from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.db.models import Q, Max
from django.utils import timezone

from apps.accounts.decorators import premium_required
from .models import Goal, Milestone, GoalProgressLog
from .forms import GoalForm, MilestoneForm, ProgressLogForm


@login_required
def goal_list(request):
    """Display list of user's goals with filtering options."""
    is_premium = request.user.profile.is_premium

    if is_premium:
        goals = Goal.objects.filter(user=request.user)

        # Apply filters
        status = request.GET.get('status')
        category = request.GET.get('category')
        priority = request.GET.get('priority')
        search = request.GET.get('q')

        if status:
            goals = goals.filter(status=status)
        if category:
            goals = goals.filter(category=category)
        if priority:
            goals = goals.filter(priority=priority)
        if search:
            goals = goals.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        # Organize by status for dashboard view
        active_goals = goals.filter(status__in=['not_started', 'in_progress'])
        completed_goals = goals.filter(status='completed')
        on_hold_goals = goals.filter(status__in=['on_hold', 'abandoned'])

        # Stats
        stats = {
            'total': goals.count(),
            'active': active_goals.count(),
            'completed': completed_goals.count(),
            'overdue': sum(1 for g in active_goals if g.is_overdue),
        }
    else:
        # Free user - empty data
        goals = []
        active_goals = []
        completed_goals = []
        on_hold_goals = []
        stats = {'total': 0, 'active': 0, 'completed': 0, 'overdue': 0}

    now = timezone.now()
    context = {
        'goals': goals,
        'active_goals': active_goals,
        'completed_goals': completed_goals,
        'on_hold_goals': on_hold_goals,
        'stats': stats,
        'status_choices': Goal.STATUS_CHOICES,
        'category_choices': Goal.CATEGORY_CHOICES,
        'priority_choices': Goal.PRIORITY_CHOICES,
        'current_filters': {
            'status': request.GET.get('status'),
            'category': request.GET.get('category'),
            'priority': request.GET.get('priority'),
            'q': request.GET.get('q'),
        },
        'active_page': 'goals',
        'current_year': now.year,
        'is_premium': is_premium,
    }
    return render(request, 'goals/goal_list.html', context)


@login_required
@premium_required
def goal_detail(request, pk):
    """Display a single goal with milestones and progress."""
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    milestones = goal.milestones.all()
    progress_logs = goal.progress_logs.all()[:10]
    linked_entries = goal.journal_entries.all()[:5]

    # Forms for inline actions
    milestone_form = MilestoneForm()
    progress_form = ProgressLogForm(initial={'value': goal.current_value})

    now = timezone.now()
    context = {
        'goal': goal,
        'milestones': milestones,
        'progress_logs': progress_logs,
        'linked_entries': linked_entries,
        'milestone_form': milestone_form,
        'progress_form': progress_form,
        'active_page': 'goals',
        'current_year': now.year,
    }
    return render(request, 'goals/goal_detail.html', context)


@login_required
@premium_required
def goal_create(request):
    """Create a new goal."""
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.title}" created successfully!')
            return redirect('goals:goal_detail', pk=goal.pk)
    else:
        form = GoalForm()

    now = timezone.now()
    context = {
        'form': form,
        'is_edit': False,
        'active_page': 'goals',
        'current_year': now.year,
    }
    return render(request, 'goals/goal_form.html', context)


@login_required
@premium_required
def goal_edit(request, pk):
    """Edit an existing goal."""
    goal = get_object_or_404(Goal, pk=pk, user=request.user)

    if request.method == 'POST':
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Goal "{goal.title}" updated successfully!')
            return redirect('goals:goal_detail', pk=goal.pk)
    else:
        form = GoalForm(instance=goal)

    now = timezone.now()
    context = {
        'form': form,
        'goal': goal,
        'is_edit': True,
        'active_page': 'goals',
        'current_year': now.year,
    }
    return render(request, 'goals/goal_form.html', context)


@login_required
@premium_required
def goal_delete(request, pk):
    """Delete a goal."""
    goal = get_object_or_404(Goal, pk=pk, user=request.user)

    if request.method == 'POST':
        title = goal.title
        goal.delete()
        messages.success(request, f'Goal "{title}" deleted.')
        return redirect('goals:goal_list')

    now = timezone.now()
    context = {
        'goal': goal,
        'active_page': 'goals',
        'current_year': now.year,
    }
    return render(request, 'goals/goal_confirm_delete.html', context)


@login_required
@premium_required
@require_POST
def goal_update_progress(request, pk):
    """AJAX endpoint to update goal progress."""
    goal = get_object_or_404(Goal, pk=pk, user=request.user)

    form = ProgressLogForm(request.POST)
    if form.is_valid():
        # Create progress log
        GoalProgressLog.objects.create(
            goal=goal,
            value=form.cleaned_data['value'],
            note=form.cleaned_data.get('note', '')
        )

        # Auto-update status if target reached
        if goal.target_value and goal.current_value >= goal.target_value:
            if goal.status != 'completed':
                goal.status = 'completed'
                goal.save()

        return JsonResponse({
            'success': True,
            'current_value': float(goal.current_value),
            'progress_percentage': goal.progress_percentage,
            'status': goal.status,
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@premium_required
@require_POST
def milestone_create(request, goal_pk):
    """Create a new milestone for a goal."""
    goal = get_object_or_404(Goal, pk=goal_pk, user=request.user)

    form = MilestoneForm(request.POST)
    if form.is_valid():
        milestone = form.save(commit=False)
        milestone.goal = goal
        # Set order to next available
        max_order = goal.milestones.aggregate(Max('order'))['order__max'] or 0
        if not milestone.order:
            milestone.order = max_order + 1
        milestone.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'milestone_id': milestone.pk,
                'title': milestone.title,
            })
        messages.success(request, f'Milestone "{milestone.title}" added.')
        return redirect('goals:goal_detail', pk=goal.pk)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    messages.error(request, 'Error creating milestone.')
    return redirect('goals:goal_detail', pk=goal.pk)


@login_required
@premium_required
@require_POST
def milestone_toggle(request, pk):
    """Toggle milestone completion status."""
    milestone = get_object_or_404(Milestone, pk=pk, goal__user=request.user)
    milestone.toggle_complete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_completed': milestone.is_completed,
            'completed_at': milestone.completed_at.isoformat() if milestone.completed_at else None,
            'goal_progress': milestone.goal.progress_percentage,
        })

    return redirect('goals:goal_detail', pk=milestone.goal.pk)


@login_required
@premium_required
@require_POST
def milestone_delete(request, pk):
    """Delete a milestone."""
    milestone = get_object_or_404(Milestone, pk=pk, goal__user=request.user)
    goal_pk = milestone.goal.pk
    milestone.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    messages.success(request, 'Milestone deleted.')
    return redirect('goals:goal_detail', pk=goal_pk)


@login_required
@premium_required
@require_POST
def goal_link_entry(request, pk):
    """Link a journal entry to a goal."""
    from apps.journal.models import Entry

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    entry_id = request.POST.get('entry_id')

    if entry_id:
        entry = get_object_or_404(Entry, pk=entry_id, user=request.user)
        goal.journal_entries.add(entry)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'entry_id': entry.pk,
                'entry_title': entry.title or f"Entry from {entry.entry_date}",
            })
        messages.success(request, 'Journal entry linked to goal.')

    return redirect('goals:goal_detail', pk=goal.pk)


@login_required
@premium_required
@require_POST
def goal_unlink_entry(request, pk):
    """Unlink a journal entry from a goal."""
    from apps.journal.models import Entry

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    entry_id = request.POST.get('entry_id')

    if entry_id:
        entry = get_object_or_404(Entry, pk=entry_id, user=request.user)
        goal.journal_entries.remove(entry)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'Journal entry unlinked from goal.')

    return redirect('goals:goal_detail', pk=goal.pk)


@login_required
@premium_required
@require_GET
def goal_entries_search(request, pk):
    """AJAX search for journal entries to link."""
    from apps.journal.models import Entry

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    query = request.GET.get('q', '')

    entries = Entry.objects.filter(user=request.user)
    if query:
        entries = entries.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    # Exclude already linked entries
    linked_ids = goal.journal_entries.values_list('pk', flat=True)
    entries = entries.exclude(pk__in=linked_ids)[:10]

    results = [{
        'id': e.pk,
        'title': e.title or f"Entry from {e.entry_date}",
        'date': e.entry_date.isoformat(),
        'preview': e.preview[:100],
    } for e in entries]

    return JsonResponse({'entries': results})


@login_required
@premium_required
@require_GET
def goal_habits_search(request, pk):
    """AJAX search for habits to link to a goal."""
    from apps.habits.models import Habit

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    query = request.GET.get('q', '')

    habits = Habit.objects.filter(user=request.user, is_active=True)
    if query:
        habits = habits.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    # Get IDs of already linked habits
    linked_ids = set(goal.linked_habits.values_list('pk', flat=True))

    results = [{
        'id': h.pk,
        'name': h.name,
        'icon': h.icon,
        'color': h.color,
        'current_streak': h.current_streak,
        'is_linked': h.pk in linked_ids,
    } for h in habits[:20]]

    return JsonResponse({'habits': results})


@login_required
@premium_required
@require_POST
def goal_link_habit(request, pk):
    """Link a habit to a goal."""
    from apps.habits.models import Habit

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    habit_id = request.POST.get('habit_id')

    if habit_id:
        habit = get_object_or_404(Habit, pk=habit_id, user=request.user)
        goal.linked_habits.add(habit)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'habit_id': habit.pk,
                'habit_name': habit.name,
            })
        messages.success(request, f'Habit "{habit.name}" linked to goal.')

    return redirect('goals:goal_detail', pk=goal.pk)


@login_required
@premium_required
@require_POST
def goal_unlink_habit(request, pk):
    """Unlink a habit from a goal."""
    from apps.habits.models import Habit

    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    habit_id = request.POST.get('habit_id')

    if habit_id:
        habit = get_object_or_404(Habit, pk=habit_id, user=request.user)
        goal.linked_habits.remove(habit)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Habit "{habit.name}" unlinked from goal.')

    return redirect('goals:goal_detail', pk=goal.pk)
