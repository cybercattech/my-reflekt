"""
Template tags for the Challenges app.
"""
from django import template
from apps.challenges.models import UserChallenge
from apps.challenges.services import get_current_prompt

register = template.Library()


@register.inclusion_tag('challenges/partials/_active_challenges_widget.html', takes_context=True)
def active_challenges_widget(context):
    """
    Render widget showing user's active challenges and today's prompts.

    Usage: {% load challenge_tags %}{% active_challenges_widget %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {'challenges': []}

    active = UserChallenge.objects.filter(
        user=request.user,
        status='active'
    ).select_related('challenge')

    challenges_data = []
    for uc in active:
        prompt = get_current_prompt(uc)
        total = uc.challenge.prompts.count()
        progress = int((uc.prompts_completed / total) * 100) if total > 0 else 0

        challenges_data.append({
            'user_challenge': uc,
            'challenge': uc.challenge,
            'current_prompt': prompt,
            'progress_percent': progress,
            'total_prompts': total,
        })

    return {'challenges': challenges_data}


@register.simple_tag
def user_challenge_status(user, challenge):
    """
    Get the user's status for a specific challenge.

    Usage: {% user_challenge_status user challenge as status %}
    """
    if not user.is_authenticated:
        return None

    uc = UserChallenge.objects.filter(
        user=user,
        challenge=challenge
    ).first()

    return uc.status if uc else None


@register.simple_tag
def challenge_prompt_completed(user_challenge, prompt):
    """
    Check if a prompt has been completed for a user challenge.

    Usage: {% challenge_prompt_completed user_challenge prompt as is_completed %}
    """
    from apps.challenges.models import ChallengeEntry

    return ChallengeEntry.objects.filter(
        user_challenge=user_challenge,
        prompt=prompt
    ).exists()
