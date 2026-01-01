"""
Admin views for managing challenges.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.text import slugify

from .models import Challenge, ChallengePrompt, UserChallenge


@staff_member_required
def challenge_admin_list(request):
    """List all challenges for admin management."""
    challenges = Challenge.objects.all().order_by('-created_at')

    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        challenges = challenges.filter(status=status)

    context = {
        'challenges': challenges,
        'title': 'Challenge Management',
        'active_page': 'admin_challenges',
        'status_filter': status,
    }
    return render(request, 'admin/challenges/challenge_list.html', context)


@staff_member_required
def challenge_create(request):
    """Create a new challenge."""
    if request.method == 'POST':
        # Get form data
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        short_description = request.POST.get('short_description', '').strip()
        cadence = request.POST.get('cadence', 'daily')
        duration_days = int(request.POST.get('duration_days', 7))
        icon = request.POST.get('icon', 'bi-trophy')
        color = request.POST.get('color', '#6366f1')
        cover_image = request.POST.get('cover_image', '').strip()
        badge_name = request.POST.get('badge_name', '').strip()
        badge_icon = request.POST.get('badge_icon', 'bi-award')
        badge_tier = request.POST.get('badge_tier', 'challenge')
        requires_premium = request.POST.get('requires_premium') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        status = request.POST.get('status', 'draft')

        # Generate unique badge_id from title
        base_badge_id = f"challenge_{slugify(title)}"
        badge_id = base_badge_id
        counter = 1
        while Challenge.objects.filter(badge_id=badge_id).exists():
            badge_id = f"{base_badge_id}_{counter}"
            counter += 1

        # Create the challenge
        challenge = Challenge.objects.create(
            title=title,
            description=description,
            short_description=short_description,
            cadence=cadence,
            duration_days=duration_days,
            icon=icon,
            color=color,
            cover_image=cover_image,
            badge_id=badge_id,
            badge_name=badge_name or f"{title} Champion",
            badge_icon=badge_icon,
            badge_tier=badge_tier,
            requires_premium=requires_premium,
            is_featured=is_featured,
            status=status,
        )

        messages.success(request, f"Challenge '{challenge.title}' created. Now add prompts!")
        return redirect('accounts:admin_challenge_prompts', pk=challenge.pk)

    context = {
        'title': 'Create Challenge',
        'active_page': 'admin_challenges',
    }
    return render(request, 'admin/challenges/challenge_form.html', context)


@staff_member_required
def challenge_edit(request, pk):
    """Edit an existing challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)

    if request.method == 'POST':
        # Update challenge fields
        challenge.title = request.POST.get('title', '').strip()
        challenge.description = request.POST.get('description', '').strip()
        challenge.short_description = request.POST.get('short_description', '').strip()
        challenge.cadence = request.POST.get('cadence', 'daily')
        challenge.duration_days = int(request.POST.get('duration_days', 7))
        challenge.icon = request.POST.get('icon', 'bi-trophy')
        challenge.color = request.POST.get('color', '#6366f1')
        challenge.cover_image = request.POST.get('cover_image', '').strip()
        challenge.badge_name = request.POST.get('badge_name', '').strip()
        challenge.badge_icon = request.POST.get('badge_icon', 'bi-award')
        challenge.badge_tier = request.POST.get('badge_tier', 'challenge')
        challenge.requires_premium = request.POST.get('requires_premium') == 'on'
        challenge.is_featured = request.POST.get('is_featured') == 'on'
        challenge.status = request.POST.get('status', 'draft')
        challenge.save()

        messages.success(request, f"Challenge '{challenge.title}' updated.")
        return redirect('accounts:admin_challenge_list')

    context = {
        'challenge': challenge,
        'title': f'Edit: {challenge.title}',
        'active_page': 'admin_challenges',
    }
    return render(request, 'admin/challenges/challenge_form.html', context)


@staff_member_required
def challenge_delete(request, pk):
    """Delete a challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)

    if request.method == 'POST':
        title = challenge.title
        challenge.delete()
        messages.success(request, f"Challenge '{title}' deleted.")
        return redirect('accounts:admin_challenge_list')

    context = {
        'challenge': challenge,
        'title': f'Delete: {challenge.title}',
        'active_page': 'admin_challenges',
    }
    return render(request, 'admin/challenges/challenge_confirm_delete.html', context)


@staff_member_required
def challenge_prompts(request, pk):
    """Manage prompts for a challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)
    prompts = challenge.prompts.all().order_by('day_number')

    context = {
        'challenge': challenge,
        'prompts': prompts,
        'title': f'Prompts: {challenge.title}',
        'active_page': 'admin_challenges',
    }
    return render(request, 'admin/challenges/prompt_list.html', context)


@staff_member_required
@require_POST
def prompt_add(request, pk):
    """Add a new prompt to a challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)

    day_number = int(request.POST.get('day_number', 1))
    title = request.POST.get('title', '').strip()
    prompt_text = request.POST.get('prompt_text', '').strip()
    guidance = request.POST.get('guidance', '').strip()
    icon = request.POST.get('icon', 'bi-journal-text')

    # Check if day_number already exists
    if ChallengePrompt.objects.filter(challenge=challenge, day_number=day_number).exists():
        messages.error(request, f"Day {day_number} already has a prompt.")
        return redirect('accounts:admin_challenge_prompts', pk=pk)

    ChallengePrompt.objects.create(
        challenge=challenge,
        day_number=day_number,
        title=title,
        prompt_text=prompt_text,
        guidance=guidance,
        icon=icon,
    )

    messages.success(request, f"Prompt for Day {day_number} added.")
    return redirect('accounts:admin_challenge_prompts', pk=pk)


@staff_member_required
@require_POST
def prompt_edit(request, pk, prompt_pk):
    """Edit an existing prompt."""
    challenge = get_object_or_404(Challenge, pk=pk)
    prompt = get_object_or_404(ChallengePrompt, pk=prompt_pk, challenge=challenge)

    prompt.title = request.POST.get('title', '').strip()
    prompt.prompt_text = request.POST.get('prompt_text', '').strip()
    prompt.guidance = request.POST.get('guidance', '').strip()
    prompt.icon = request.POST.get('icon', 'bi-journal-text')
    prompt.save()

    messages.success(request, f"Prompt for Day {prompt.day_number} updated.")
    return redirect('accounts:admin_challenge_prompts', pk=pk)


@staff_member_required
@require_POST
def prompt_delete(request, pk, prompt_pk):
    """Delete a prompt."""
    challenge = get_object_or_404(Challenge, pk=pk)
    prompt = get_object_or_404(ChallengePrompt, pk=prompt_pk, challenge=challenge)

    day_number = prompt.day_number
    prompt.delete()

    messages.success(request, f"Prompt for Day {day_number} deleted.")
    return redirect('accounts:admin_challenge_prompts', pk=pk)


@staff_member_required
def challenge_stats(request, pk):
    """View participation stats for a challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)
    participants = UserChallenge.objects.filter(
        challenge=challenge
    ).select_related('user', 'user__profile').order_by('-started_at')

    context = {
        'challenge': challenge,
        'participants': participants,
        'active_count': participants.filter(status='active').count(),
        'completed_count': participants.filter(status='completed').count(),
        'failed_count': participants.filter(status='failed').count(),
        'abandoned_count': participants.filter(status='abandoned').count(),
        'title': f'Stats: {challenge.title}',
        'active_page': 'admin_challenges',
    }
    return render(request, 'admin/challenges/challenge_stats.html', context)
