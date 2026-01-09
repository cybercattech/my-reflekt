"""
Wellness tracking views for pain, intimacy, cycle tracking, and body fitness.
"""
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg
from django.contrib import messages
from datetime import timedelta, date
import json

from .models import (
    PainLog, IntimacyLog, CycleLog, CyclePrediction,
    BodyMetric, CardioLog, FitnessGoal, FitnessGoalProgress
)
from .forms import (
    BodyMetricForm, CardioLogForm, FitnessGoalForm,
    FitnessGoalProgressForm, QuickWeightForm
)
from .services import (
    get_pain_correlations,
    get_pain_by_location,
    get_pain_by_day_of_week,
    get_recent_pain_logs,
)


@login_required
def wellness_dashboard(request):
    """Main wellness overview dashboard."""
    user = request.user
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Pain stats
    pain_this_month = PainLog.objects.filter(
        user=user,
        logged_at__gte=thirty_days_ago
    ).count()

    avg_pain_intensity = PainLog.objects.filter(
        user=user,
        logged_at__gte=thirty_days_ago
    ).aggregate(avg=Avg('intensity'))['avg'] or 0

    # Recent pain logs
    recent_pain = PainLog.objects.filter(user=user)[:5]

    # Intimacy stats (discreet)
    intimacy_this_month = IntimacyLog.objects.filter(
        user=user,
        logged_at__gte=thirty_days_ago
    ).count()

    last_intimacy = IntimacyLog.objects.filter(user=user).first()

    # Cycle stats
    last_period = CycleLog.objects.filter(
        user=user,
        person__isnull=True,
        event_type='period_start'
    ).first()

    cycle_prediction = CyclePrediction.objects.filter(
        user=user,
        person__isnull=True
    ).first()

    # Fitness stats
    latest_metric = BodyMetric.objects.filter(user=user).first()

    # Weight change (compare to previous)
    weight_change = None
    if latest_metric and latest_metric.weight:
        previous_metric = BodyMetric.objects.filter(
            user=user,
            weight__isnull=False
        ).exclude(pk=latest_metric.pk).first()
        if previous_metric and previous_metric.weight:
            weight_change = float(latest_metric.weight) - float(previous_metric.weight)

    # Cardio stats this month
    cardio_this_month = CardioLog.objects.filter(
        user=user,
        logged_at__gte=thirty_days_ago
    )
    total_distance = sum(float(c.distance or 0) for c in cardio_this_month)
    cardio_count = cardio_this_month.count()

    # Active fitness goals
    active_fitness_goals = FitnessGoal.objects.filter(
        user=user,
        is_active=True,
        is_completed=False
    )[:3]

    # Get user wellness settings
    profile = user.profile
    enable_intimacy = profile.enable_intimacy_tracking
    enable_cycle = profile.enable_cycle_tracking

    context = {
        'pain_this_month': pain_this_month,
        'avg_pain_intensity': round(avg_pain_intensity, 1),
        'recent_pain': recent_pain,
        'intimacy_this_month': intimacy_this_month,
        'last_intimacy': last_intimacy,
        'last_period': last_period,
        'cycle_prediction': cycle_prediction,
        'enable_intimacy': enable_intimacy,
        'enable_cycle': enable_cycle,
        # Fitness data
        'latest_metric': latest_metric,
        'weight_change': weight_change,
        'total_distance': round(total_distance, 1),
        'cardio_count': cardio_count,
        'active_fitness_goals': active_fitness_goals,
    }

    return render(request, 'wellness/dashboard.html', context)


@login_required
def pain_dashboard(request):
    """Pain tracking analytics dashboard."""
    user = request.user
    days = int(request.GET.get('days', 90))
    start_date = timezone.now() - timedelta(days=days)

    # Get pain data
    pain_logs = PainLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    # Statistics
    total_episodes = pain_logs.count()
    avg_intensity = pain_logs.aggregate(avg=Avg('intensity'))['avg'] or 0

    # By location
    by_location = get_pain_by_location(user, days)

    # By day of week
    by_day = get_pain_by_day_of_week(user, days)

    # Correlations
    correlations = get_pain_correlations(user, days)

    # Recent logs
    recent_logs = get_recent_pain_logs(user, limit=20)

    context = {
        'days': days,
        'total_episodes': total_episodes,
        'avg_intensity': round(avg_intensity, 1),
        'by_location': by_location,
        'by_day': by_day,
        'correlations': correlations,
        'recent_logs': recent_logs,
        'location_choices': PainLog.LOCATION_CHOICES,
        'pain_type_choices': PainLog.PAIN_TYPE_CHOICES,
        'duration_choices': PainLog.DURATION_CHOICES,
    }

    return render(request, 'wellness/pain_dashboard.html', context)


@login_required
def pain_quick_log(request):
    """Quick standalone pain logging page."""
    context = {
        'location_choices': PainLog.LOCATION_CHOICES,
        'pain_type_choices': PainLog.PAIN_TYPE_CHOICES,
        'duration_choices': PainLog.DURATION_CHOICES,
    }
    return render(request, 'wellness/pain_quick_log.html', context)


@login_required
def intimacy_dashboard(request):
    """Discreet intimacy tracking dashboard."""
    user = request.user
    days = int(request.GET.get('days', 180))
    start_date = timezone.now() - timedelta(days=days)

    logs = IntimacyLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    # Monthly counts for heatmap
    monthly_counts = {}
    for log in logs:
        month_key = log.logged_at.strftime('%Y-%m')
        monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

    context = {
        'days': days,
        'total_count': logs.count(),
        'monthly_counts': json.dumps(monthly_counts),
        'recent_logs': logs[:10],
    }

    return render(request, 'wellness/intimacy_dashboard.html', context)


@login_required
def cycle_dashboard(request):
    """Cycle tracking dashboard with predictions."""
    user = request.user
    person_id = request.GET.get('person')

    # Get person filter (None = self)
    person = None
    if person_id:
        from apps.accounts.models import FamilyMember
        person = get_object_or_404(FamilyMember, pk=person_id, user=user)

    # Get cycle logs
    logs = CycleLog.objects.filter(
        user=user,
        person=person
    )[:50]

    # Get period starts for cycle length calculation
    period_starts = CycleLog.objects.filter(
        user=user,
        person=person,
        event_type='period_start'
    ).order_by('-log_date')[:12]

    # Get prediction
    prediction = CyclePrediction.objects.filter(
        user=user,
        person=person
    ).first()

    # Family members for toggle
    from apps.accounts.models import FamilyMember
    family_members = FamilyMember.objects.filter(user=user)

    context = {
        'logs': logs,
        'period_starts': period_starts,
        'prediction': prediction,
        'selected_person': person,
        'family_members': family_members,
        'event_choices': CycleLog.EVENT_TYPE_CHOICES,
        'flow_choices': CycleLog.FLOW_LEVEL_CHOICES,
        'symptom_choices': CycleLog.SYMPTOM_CHOICES,
    }

    return render(request, 'wellness/cycle_dashboard.html', context)


@login_required
def cycle_calendar(request):
    """Visual calendar view for cycle tracking."""
    user = request.user
    person_id = request.GET.get('person')

    person = None
    if person_id:
        from apps.accounts.models import FamilyMember
        person = get_object_or_404(FamilyMember, pk=person_id, user=user)

    # Get last 6 months of data
    start_date = timezone.now().date() - timedelta(days=180)
    logs = CycleLog.objects.filter(
        user=user,
        person=person,
        log_date__gte=start_date
    )

    # Format for calendar
    calendar_data = []
    for log in logs:
        calendar_data.append({
            'date': log.log_date.isoformat(),
            'type': log.event_type,
            'flow': log.flow_level,
            'symptoms': log.symptoms,
        })

    context = {
        'calendar_data': json.dumps(calendar_data),
        'selected_person': person,
    }

    return render(request, 'wellness/cycle_calendar.html', context)


# =============================================================================
# API Endpoints
# =============================================================================

@login_required
@require_http_methods(["POST"])
def api_pain_log(request):
    """Create a new pain log entry."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    location = data.get('location')
    intensity = data.get('intensity')

    if not location or not intensity:
        return JsonResponse({'error': 'Location and intensity are required'}, status=400)

    try:
        intensity = int(intensity)
        if not 1 <= intensity <= 10:
            raise ValueError()
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Intensity must be 1-10'}, status=400)

    # Handle custom time
    user_time = data.get('time')
    logged_at = None
    if user_time:
        try:
            from datetime import datetime, time as dt_time
            hours, minutes = map(int, user_time.split(':'))
            pain_time = dt_time(hours, minutes)
            today = timezone.now().date()
            logged_at = datetime.combine(today, pain_time)
            logged_at = timezone.make_aware(logged_at) if timezone.is_naive(logged_at) else logged_at
        except (ValueError, TypeError):
            pass  # Fall back to default (now)

    # Create pain log
    create_kwargs = {
        'user': request.user,
        'location': location,
        'intensity': intensity,
        'pain_type': data.get('pain_type', ''),
        'duration': data.get('duration', ''),
        'notes': data.get('notes', ''),
        'triggers': data.get('triggers', []),
    }
    if logged_at:
        create_kwargs['logged_at'] = logged_at

    pain_log = PainLog.objects.create(**create_kwargs)

    return JsonResponse({
        'success': True,
        'id': pain_log.pk,
        'message': f'Pain logged: {pain_log.location_display} ({intensity}/10)',
    })


@login_required
@require_http_methods(["POST"])
def api_pain_delete(request, pk):
    """Delete a pain log entry."""
    pain_log = get_object_or_404(PainLog, pk=pk, user=request.user)
    pain_log.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_intimacy_log(request):
    """Create a new intimacy log entry."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    log = IntimacyLog.objects.create(
        user=request.user,
        rating=data.get('rating'),
        notes=data.get('notes', ''),
    )

    return JsonResponse({
        'success': True,
        'id': log.pk,
        'message': '🍀 Logged',
    })


@login_required
@require_http_methods(["POST"])
def api_cycle_log(request):
    """Create a new cycle log entry."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event_type = data.get('event_type')
    if not event_type:
        return JsonResponse({'error': 'Event type is required'}, status=400)

    # Get person (optional)
    person = None
    person_id = data.get('person_id')
    if person_id:
        from apps.accounts.models import FamilyMember
        person = get_object_or_404(FamilyMember, pk=person_id, user=request.user)

    log = CycleLog.objects.create(
        user=request.user,
        person=person,
        event_type=event_type,
        flow_level=data.get('flow_level', ''),
        symptoms=data.get('symptoms', []),
        notes=data.get('notes', ''),
    )

    # Update prediction if period started
    if event_type == 'period_start':
        from .services import update_cycle_prediction
        update_cycle_prediction(request.user, person)

    return JsonResponse({
        'success': True,
        'id': log.pk,
        'message': f'Cycle event logged: {log.event_display}',
    })


@login_required
@require_http_methods(["GET"])
def api_correlations(request):
    """Get wellness correlation data."""
    user = request.user
    days = int(request.GET.get('days', 90))

    correlations = get_pain_correlations(user, days)

    return JsonResponse({
        'correlations': correlations,
    })


# =============================================================================
# Body Fitness Views
# =============================================================================

@login_required
def fitness_dashboard(request):
    """Main fitness tracking dashboard."""
    user = request.user
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Latest body metrics
    latest_metric = BodyMetric.objects.filter(user=user).first()
    previous_metric = BodyMetric.objects.filter(user=user)[1:2].first() if latest_metric else None

    # Calculate weight change
    weight_change = None
    if latest_metric and previous_metric and latest_metric.weight and previous_metric.weight:
        weight_change = float(latest_metric.weight) - float(previous_metric.weight)

    # Recent cardio logs
    recent_cardio = CardioLog.objects.filter(user=user)[:5]

    # Cardio stats this month
    cardio_this_month = CardioLog.objects.filter(
        user=user,
        logged_at__gte=thirty_days_ago
    )
    total_distance = sum(float(c.distance) for c in cardio_this_month)
    cardio_count = cardio_this_month.count()

    # Active fitness goals
    active_goals = FitnessGoal.objects.filter(
        user=user,
        is_active=True,
        is_completed=False
    )[:4]

    # Completed goals count
    completed_goals_count = FitnessGoal.objects.filter(
        user=user,
        is_completed=True
    ).count()

    # Weight history for chart (last 30 days)
    weight_history = BodyMetric.objects.filter(
        user=user,
        weight__isnull=False,
        logged_at__gte=thirty_days_ago
    ).order_by('logged_at').values('logged_at', 'weight')

    weight_chart_data = [
        {
            'date': m['logged_at'].strftime('%Y-%m-%d'),
            'weight': float(m['weight'])
        }
        for m in weight_history
    ]

    context = {
        'latest_metric': latest_metric,
        'weight_change': weight_change,
        'recent_cardio': recent_cardio,
        'total_distance': round(total_distance, 2),
        'cardio_count': cardio_count,
        'active_goals': active_goals,
        'completed_goals_count': completed_goals_count,
        'weight_chart_data': json.dumps(weight_chart_data),
    }

    return render(request, 'wellness/fitness_dashboard.html', context)


@login_required
def body_metrics(request):
    """Body measurements history and logging."""
    user = request.user
    days = int(request.GET.get('days', 90))
    start_date = timezone.now() - timedelta(days=days)

    # Get metrics history
    metrics = BodyMetric.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    # Latest measurements
    latest = BodyMetric.objects.filter(user=user).first()

    # Weight trend data
    weight_data = BodyMetric.objects.filter(
        user=user,
        weight__isnull=False,
        logged_at__gte=start_date
    ).order_by('logged_at').values('logged_at', 'weight')

    weight_chart = [
        {'date': m['logged_at'].strftime('%Y-%m-%d'), 'value': float(m['weight'])}
        for m in weight_data
    ]

    context = {
        'metrics': metrics,
        'latest': latest,
        'days': days,
        'weight_chart': json.dumps(weight_chart),
        'form': BodyMetricForm(),
    }

    return render(request, 'wellness/body_metrics.html', context)


@login_required
def cardio_log_view(request):
    """Cardio activity history and logging."""
    user = request.user
    days = int(request.GET.get('days', 90))
    activity_filter = request.GET.get('activity', '')
    start_date = timezone.now() - timedelta(days=days)

    # Get cardio logs
    logs = CardioLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    if activity_filter:
        logs = logs.filter(activity_type=activity_filter)

    # Stats
    total_distance = sum(float(l.distance) for l in logs)
    total_time = sum(l.total_minutes_decimal for l in logs)
    avg_pace = total_time / total_distance if total_distance > 0 else 0

    # Chart data - distance over time
    distance_chart = [
        {
            'date': l.logged_at.strftime('%Y-%m-%d'),
            'distance': float(l.distance),
            'pace': l.pace or 0
        }
        for l in logs.order_by('logged_at')
    ]

    context = {
        'logs': logs,
        'days': days,
        'activity_filter': activity_filter,
        'total_distance': round(total_distance, 2),
        'total_time': int(total_time),
        'avg_pace': round(avg_pace, 2) if avg_pace else 0,
        'distance_chart': json.dumps(distance_chart),
        'activity_choices': CardioLog.ACTIVITY_TYPE_CHOICES,
        'form': CardioLogForm(),
    }

    return render(request, 'wellness/cardio_log.html', context)


@login_required
def fitness_goals(request):
    """List all fitness goals."""
    user = request.user

    active_goals = FitnessGoal.objects.filter(
        user=user,
        is_active=True,
        is_completed=False
    )

    completed_goals = FitnessGoal.objects.filter(
        user=user,
        is_completed=True
    )[:10]

    inactive_goals = FitnessGoal.objects.filter(
        user=user,
        is_active=False,
        is_completed=False
    )

    context = {
        'active_goals': active_goals,
        'completed_goals': completed_goals,
        'inactive_goals': inactive_goals,
    }

    return render(request, 'wellness/fitness_goals.html', context)


@login_required
def create_fitness_goal(request):
    """Create a new fitness goal."""
    if request.method == 'POST':
        form = FitnessGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.current_value = goal.start_value
            goal.save()
            messages.success(request, f'Goal "{goal.title}" created!')
            return redirect('wellness:fitness_goals')
    else:
        form = FitnessGoalForm()

    context = {
        'form': form,
        'title': 'Create Fitness Goal',
    }

    return render(request, 'wellness/fitness_goal_form.html', context)


@login_required
def fitness_goal_detail(request, pk):
    """View a single fitness goal with progress."""
    goal = get_object_or_404(FitnessGoal, pk=pk, user=request.user)

    # Progress history (most recent first for display)
    progress_entries = goal.progress_entries.all()[:20]

    # Chart data - progress over time (oldest first for chart)
    chart_entries = goal.progress_entries.order_by('logged_at')[:50]
    progress_chart = []
    for entry in chart_entries:
        progress_chart.append({
            'date': entry.logged_at.strftime('%Y-%m-%d'),
            'value': float(entry.value),
        })

    # Generate expected line data points
    expected_line = []
    if goal.start_date and goal.target_date:
        current_date = goal.start_date
        total_days = (goal.target_date - goal.start_date).days
        while current_date <= goal.target_date:
            days_elapsed = (current_date - goal.start_date).days
            progress_ratio = days_elapsed / total_days if total_days > 0 else 1
            expected = float(goal.start_value) + (float(goal.target_value) - float(goal.start_value)) * progress_ratio
            expected_line.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'value': round(expected, 2)
            })
            current_date += timedelta(days=7)  # Weekly points

    context = {
        'goal': goal,
        'progress_entries': progress_entries,
        'progress_chart': json.dumps(progress_chart),
        'expected_line': json.dumps(expected_line),
        'progress_form': FitnessGoalProgressForm(),
    }

    return render(request, 'wellness/fitness_goal_detail.html', context)


@login_required
def edit_fitness_goal(request, pk):
    """Edit an existing fitness goal."""
    goal = get_object_or_404(FitnessGoal, pk=pk, user=request.user)

    if request.method == 'POST':
        form = FitnessGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Goal "{goal.title}" updated!')
            return redirect('wellness:fitness_goal_detail', pk=goal.pk)
    else:
        form = FitnessGoalForm(instance=goal)

    context = {
        'form': form,
        'goal': goal,
        'title': 'Edit Fitness Goal',
    }

    return render(request, 'wellness/fitness_goal_form.html', context)


@login_required
def delete_fitness_goal(request, pk):
    """Delete a fitness goal."""
    goal = get_object_or_404(FitnessGoal, pk=pk, user=request.user)

    if request.method == 'POST':
        title = goal.title
        goal.delete()
        messages.success(request, f'Goal "{title}" deleted.')
        return redirect('wellness:fitness_goals')

    context = {
        'goal': goal,
    }

    return render(request, 'wellness/fitness_goal_delete.html', context)


# =============================================================================
# Fitness API Endpoints
# =============================================================================

@login_required
@require_http_methods(["POST"])
def api_log_body_metric(request):
    """Create a new body metric entry."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Create metric
    metric = BodyMetric.objects.create(
        user=request.user,
        weight=data.get('weight') or None,
        weight_unit=data.get('weight_unit', 'lbs'),
        waist=data.get('waist') or None,
        chest=data.get('chest') or None,
        biceps=data.get('biceps') or None,
        thighs=data.get('thighs') or None,
        hips=data.get('hips') or None,
        body_fat=data.get('body_fat') or None,
        measurement_unit=data.get('measurement_unit', 'in'),
        notes=data.get('notes', ''),
    )

    # Auto-update related fitness goals
    _auto_update_fitness_goals(request.user, metric)

    return JsonResponse({
        'success': True,
        'id': metric.pk,
        'message': 'Body metrics logged successfully!',
    })


@login_required
@require_http_methods(["POST"])
def api_log_cardio(request):
    """Create a new cardio log entry."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    distance = data.get('distance')
    duration_minutes = data.get('duration_minutes')

    if not distance or not duration_minutes:
        return JsonResponse({'error': 'Distance and duration are required'}, status=400)

    # Create cardio log
    log = CardioLog.objects.create(
        user=request.user,
        activity_type=data.get('activity_type', 'run'),
        distance=Decimal(str(distance)),
        duration_minutes=int(duration_minutes),
        duration_seconds=int(data.get('duration_seconds', 0)),
        notes=data.get('notes', ''),
    )

    # Auto-update related fitness goals
    _auto_update_cardio_goals(request.user, log)

    return JsonResponse({
        'success': True,
        'id': log.pk,
        'pace': log.pace_display,
        'message': f'{log.activity_display} logged: {log.distance}mi in {log.duration_display}',
    })


@login_required
@require_http_methods(["POST"])
def api_update_fitness_goal_progress(request, pk):
    """Update progress on a fitness goal."""
    goal = get_object_or_404(FitnessGoal, pk=pk, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    value = data.get('value')
    if value is None:
        return JsonResponse({'error': 'Value is required'}, status=400)

    try:
        value = Decimal(str(value))
    except:
        return JsonResponse({'error': 'Invalid value'}, status=400)

    # Create progress entry
    progress = FitnessGoalProgress.objects.create(
        goal=goal,
        value=value,
        notes=data.get('notes', '')
    )

    # Update goal's current value
    goal.update_progress(value)

    return JsonResponse({
        'success': True,
        'progress_id': progress.pk,
        'current_value': float(goal.current_value),
        'progress_percentage': goal.progress_percentage,
        'is_on_track': goal.is_on_track,
        'variance': goal.variance_display,
        'is_completed': goal.is_completed,
        'message': 'Progress updated!',
    })


@login_required
@require_http_methods(["POST"])
def api_delete_body_metric(request, pk):
    """Delete a body metric entry."""
    metric = get_object_or_404(BodyMetric, pk=pk, user=request.user)
    metric.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_delete_cardio_log(request, pk):
    """Delete a cardio log entry."""
    log = get_object_or_404(CardioLog, pk=pk, user=request.user)
    log.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def api_weight_chart_data(request):
    """Get weight chart data for a specific period."""
    user = request.user
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    metrics = BodyMetric.objects.filter(
        user=user,
        weight__isnull=False,
        logged_at__gte=start_date
    ).order_by('logged_at').values('logged_at', 'weight')

    data = [
        {'date': m['logged_at'].strftime('%Y-%m-%d'), 'weight': float(m['weight'])}
        for m in metrics
    ]

    return JsonResponse({'data': data})


@login_required
@require_http_methods(["GET"])
def api_cardio_chart_data(request):
    """Get cardio chart data for a specific period."""
    user = request.user
    days = int(request.GET.get('days', 30))
    activity = request.GET.get('activity', '')
    start_date = timezone.now() - timedelta(days=days)

    logs = CardioLog.objects.filter(
        user=user,
        logged_at__gte=start_date
    )

    if activity:
        logs = logs.filter(activity_type=activity)

    logs = logs.order_by('logged_at')

    data = [
        {
            'date': l.logged_at.strftime('%Y-%m-%d'),
            'distance': float(l.distance),
            'duration': l.total_minutes_decimal,
            'pace': l.pace or 0
        }
        for l in logs
    ]

    return JsonResponse({'data': data})


# =============================================================================
# Helper Functions
# =============================================================================

def _auto_update_fitness_goals(user, metric):
    """Auto-update related fitness goals when body metrics are logged."""
    # Update weight goals
    if metric.weight:
        weight_goals = FitnessGoal.objects.filter(
            user=user,
            goal_type='weight',
            measurement_type='weight',
            is_active=True,
            is_completed=False
        )
        for goal in weight_goals:
            # Create progress entry
            FitnessGoalProgress.objects.create(
                goal=goal,
                value=metric.weight,
                notes=f'Auto-logged from body metrics'
            )
            goal.update_progress(metric.weight)

    # Update measurement goals
    measurement_fields = ['waist', 'chest', 'biceps', 'thighs', 'hips', 'body_fat']
    for field in measurement_fields:
        value = getattr(metric, field, None)
        if value:
            measurement_goals = FitnessGoal.objects.filter(
                user=user,
                goal_type='measurement',
                measurement_type=field,
                is_active=True,
                is_completed=False
            )
            for goal in measurement_goals:
                FitnessGoalProgress.objects.create(
                    goal=goal,
                    value=value,
                    notes=f'Auto-logged from body metrics'
                )
                goal.update_progress(value)


def _auto_update_cardio_goals(user, cardio_log):
    """Auto-update related fitness goals when cardio is logged."""
    # Update cardio time goals (same distance)
    time_goals = FitnessGoal.objects.filter(
        user=user,
        goal_type='cardio_time',
        activity_type=cardio_log.activity_type,
        is_active=True,
        is_completed=False
    )

    for goal in time_goals:
        # Only update if distance matches target
        if goal.target_distance and abs(float(cardio_log.distance) - float(goal.target_distance)) < 0.1:
            # For time goals, value is duration in minutes
            duration = cardio_log.total_minutes_decimal
            FitnessGoalProgress.objects.create(
                goal=goal,
                value=Decimal(str(round(duration, 2))),
                notes=f'Auto-logged: {cardio_log.distance}mi in {cardio_log.duration_display}'
            )
            goal.update_progress(Decimal(str(round(duration, 2))))

    # Update cardio distance goals
    distance_goals = FitnessGoal.objects.filter(
        user=user,
        goal_type='cardio_distance',
        activity_type=cardio_log.activity_type,
        is_active=True,
        is_completed=False
    )

    for goal in distance_goals:
        FitnessGoalProgress.objects.create(
            goal=goal,
            value=cardio_log.distance,
            notes=f'Auto-logged: {cardio_log.distance}mi'
        )
        # For cumulative distance goals, add to current value
        if goal.current_value:
            new_total = goal.current_value + cardio_log.distance
        else:
            new_total = cardio_log.distance
        goal.update_progress(new_total)
