"""
User-facing views for the Challenges app.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import F

from .models import Challenge, ChallengePrompt, UserChallenge, ChallengeEntry
from .services import calculate_end_date, get_current_prompt, check_on_time, get_user_active_challenges
from apps.journal.models import Entry


@login_required
def challenge_list(request):
    """Browse available challenges."""
    # Get all active challenges
    challenges = Challenge.objects.filter(status='active').prefetch_related('prompts')

    # Get user's participations
    user_participations = UserChallenge.objects.filter(
        user=request.user
    ).values_list('challenge_id', 'status')

    participation_map = {cp[0]: cp[1] for cp in user_participations}

    # Annotate challenges with user status
    for challenge in challenges:
        challenge.user_status = participation_map.get(challenge.id)
        challenge.prompt_count = challenge.prompts.count()

    # Get featured challenges
    featured = [c for c in challenges if c.is_featured]

    context = {
        'challenges': challenges,
        'featured_challenges': featured[:3],
        'title': 'Challenges',
        'active_page': 'challenges',
    }
    return render(request, 'challenges/challenge_list.html', context)


@login_required
def challenge_detail(request, slug):
    """View challenge details and prompts."""
    challenge = get_object_or_404(Challenge, slug=slug)
    prompts = challenge.prompts.all().order_by('day_number')

    # Check if user is participating
    user_challenge = UserChallenge.objects.filter(
        user=request.user,
        challenge=challenge
    ).first()

    # Check premium requirement
    can_join = True
    if challenge.requires_premium:
        profile = request.user.profile
        if not profile.is_premium:
            can_join = False

    context = {
        'challenge': challenge,
        'prompts': prompts,
        'user_challenge': user_challenge,
        'can_join': can_join and not user_challenge,
        'title': challenge.title,
        'active_page': 'challenges',
    }
    return render(request, 'challenges/challenge_detail.html', context)


@login_required
@require_POST
def join_challenge(request, slug):
    """User joins a challenge."""
    challenge = get_object_or_404(Challenge, slug=slug, status='active')

    # Check premium requirement
    if challenge.requires_premium:
        profile = request.user.profile
        if not profile.is_premium:
            messages.error(request, "This challenge requires a premium subscription.")
            return redirect('challenges:detail', slug=slug)

    # Check if already participating
    existing = UserChallenge.objects.filter(user=request.user, challenge=challenge).first()
    if existing:
        if existing.status == 'active':
            messages.info(request, "You're already participating in this challenge.")
            return redirect('challenges:progress', slug=slug)
        elif existing.status in ('completed', 'failed', 'abandoned'):
            # Allow restarting
            existing.delete()

    # Create participation
    today = timezone.now().date()
    end_date = calculate_end_date(today, challenge.cadence, challenge.duration_days)

    UserChallenge.objects.create(
        user=request.user,
        challenge=challenge,
        start_date=today,
        expected_end_date=end_date,
    )

    # Update challenge participant count
    Challenge.objects.filter(pk=challenge.pk).update(
        participant_count=F('participant_count') + 1
    )

    messages.success(request, f"You've joined the {challenge.title} challenge! Let's get started.")
    return redirect('challenges:progress', slug=slug)


@login_required
def challenge_progress(request, slug):
    """View user's progress in a challenge."""
    challenge = get_object_or_404(Challenge, slug=slug)
    user_challenge = get_object_or_404(
        UserChallenge,
        user=request.user,
        challenge=challenge
    )

    # Get all prompts with completion status
    all_prompts = challenge.prompts.all().order_by('day_number')
    completed_entries = ChallengeEntry.objects.filter(
        user_challenge=user_challenge
    ).select_related('prompt', 'entry')

    completed_map = {ce.prompt.day_number: ce for ce in completed_entries}

    prompts_data = []
    for prompt in all_prompts:
        entry = completed_map.get(prompt.day_number)
        prompts_data.append({
            'prompt': prompt,
            'entry': entry,
            'is_completed': entry is not None,
            'is_current': prompt.day_number == user_challenge.current_day and user_challenge.status == 'active',
        })

    # Get today's prompt
    today_prompt = get_current_prompt(user_challenge) if user_challenge.status == 'active' else None

    context = {
        'challenge': challenge,
        'user_challenge': user_challenge,
        'prompts_data': prompts_data,
        'today_prompt': today_prompt,
        'total_prompts': all_prompts.count(),
        'title': f'{challenge.title} - Progress',
        'active_page': 'challenges',
    }
    return render(request, 'challenges/challenge_progress.html', context)


@login_required
@require_POST
def submit_challenge_entry(request, slug, day_number):
    """Link a journal entry to a challenge prompt."""
    challenge = get_object_or_404(Challenge, slug=slug)
    user_challenge = get_object_or_404(
        UserChallenge,
        user=request.user,
        challenge=challenge,
        status='active'
    )
    prompt = get_object_or_404(ChallengePrompt, challenge=challenge, day_number=day_number)
    entry_id = request.POST.get('entry_id')

    if not entry_id:
        return JsonResponse({'success': False, 'error': 'No entry specified'}, status=400)

    entry = get_object_or_404(Entry, pk=entry_id, user=request.user)

    # Check if already submitted for this prompt
    existing = ChallengeEntry.objects.filter(
        user_challenge=user_challenge,
        prompt=prompt
    ).first()

    if existing:
        # Update with new entry
        existing.entry = entry
        existing.is_on_time = check_on_time(user_challenge, prompt)
        existing.save()
    else:
        # Create new challenge entry
        ChallengeEntry.objects.create(
            user_challenge=user_challenge,
            prompt=prompt,
            entry=entry,
            is_on_time=check_on_time(user_challenge, prompt),
        )

    # Note: progress update and completion check happen via signals

    return JsonResponse({
        'success': True,
        'prompts_completed': user_challenge.prompts_completed,
        'is_completed': user_challenge.status == 'completed',
    })


@login_required
@require_POST
def abandon_challenge(request, slug):
    """User abandons a challenge."""
    challenge = get_object_or_404(Challenge, slug=slug)
    user_challenge = get_object_or_404(
        UserChallenge,
        user=request.user,
        challenge=challenge,
        status='active'
    )

    user_challenge.status = 'abandoned'
    user_challenge.save()

    messages.info(request, f"You've left the {challenge.title} challenge. You can rejoin anytime!")
    return redirect('challenges:list')


@login_required
def get_active_challenges_api(request):
    """API endpoint to get user's active challenges."""
    active_challenges = get_user_active_challenges(request.user)

    data = []
    for uc in active_challenges:
        prompt = get_current_prompt(uc)
        data.append({
            'id': uc.challenge.id,
            'slug': uc.challenge.slug,
            'title': uc.challenge.title,
            'color': uc.challenge.color,
            'icon': uc.challenge.icon,
            'current_day': uc.current_day,
            'total_days': uc.challenge.duration_days,
            'progress_percent': uc.progress_percent,
            'current_prompt': {
                'day_number': prompt.day_number,
                'title': prompt.title,
                'prompt_text': prompt.prompt_text,
            } if prompt else None,
        })

    return JsonResponse({'challenges': data})
