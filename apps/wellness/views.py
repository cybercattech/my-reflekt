"""
Wellness tracking views for pain, intimacy, and cycle tracking.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg
from datetime import timedelta
import json

from .models import PainLog, IntimacyLog, CycleLog, CyclePrediction
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
