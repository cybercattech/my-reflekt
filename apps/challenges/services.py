"""
Service functions for the Challenges app.
"""
from datetime import timedelta
from django.utils import timezone


def calculate_end_date(start_date, cadence, duration_days):
    """
    Calculate expected end date based on cadence and duration.

    Args:
        start_date: The date the user started the challenge
        cadence: 'daily', 'weekly', or 'monthly'
        duration_days: Number of prompts in the challenge

    Returns:
        Expected end date
    """
    if cadence == 'daily':
        # For daily challenges, duration_days is the number of days
        return start_date + timedelta(days=duration_days - 1)
    elif cadence == 'weekly':
        # For weekly challenges, duration_days is the number of weeks
        return start_date + timedelta(weeks=duration_days)
    elif cadence == 'monthly':
        # For monthly challenges, approximate 30 days per month
        return start_date + timedelta(days=duration_days * 30)

    # Default fallback
    return start_date + timedelta(days=duration_days)


def get_current_prompt(user_challenge):
    """
    Get the current prompt the user should work on.

    For daily challenges, this is based on calendar days since start.
    For weekly/monthly, this is based on prompts_completed + 1.
    """
    from .models import ChallengePrompt

    challenge = user_challenge.challenge

    if challenge.cadence == 'daily':
        # Calculate which day they're on based on calendar
        days_since_start = (timezone.now().date() - user_challenge.start_date).days
        current_day = min(days_since_start + 1, challenge.duration_days)
    else:
        # For weekly/monthly, use prompts_completed + 1
        current_day = min(user_challenge.prompts_completed + 1, challenge.duration_days)

    return ChallengePrompt.objects.filter(
        challenge=challenge,
        day_number=current_day
    ).first()


def check_on_time(user_challenge, prompt):
    """
    Check if a submission is on time for the cadence.

    Returns True if the user is submitting within the expected timeframe.
    """
    challenge = user_challenge.challenge
    today = timezone.now().date()

    if challenge.cadence == 'daily':
        # For daily, check if submitting on the correct day
        expected_day = (today - user_challenge.start_date).days + 1
        return prompt.day_number <= expected_day
    elif challenge.cadence == 'weekly':
        # For weekly, check if within the correct week
        weeks_since_start = (today - user_challenge.start_date).days // 7
        return prompt.day_number <= weeks_since_start + 1
    elif challenge.cadence == 'monthly':
        # For monthly, check if within the correct month
        months_since_start = (today - user_challenge.start_date).days // 30
        return prompt.day_number <= months_since_start + 1

    return True


def get_user_active_challenges(user):
    """
    Get all active challenges for a user.

    Returns queryset of UserChallenge objects with status='active'.
    """
    from .models import UserChallenge

    return UserChallenge.objects.filter(
        user=user,
        status='active'
    ).select_related('challenge')


def update_challenge_progress(user_challenge):
    """
    Update the progress tracking for a user challenge.

    Called after a ChallengeEntry is created.
    """
    from .models import ChallengeEntry

    # Count completed prompts
    completed = ChallengeEntry.objects.filter(user_challenge=user_challenge).count()
    user_challenge.prompts_completed = completed

    # Update current day for display
    if user_challenge.challenge.cadence == 'daily':
        user_challenge.current_day = min(completed + 1, user_challenge.challenge.duration_days)
    else:
        user_challenge.current_day = min(completed + 1, user_challenge.challenge.duration_days)

    # Update last entry date
    user_challenge.last_entry_date = timezone.now().date()

    user_challenge.save(update_fields=['prompts_completed', 'current_day', 'last_entry_date'])

    return completed


def check_challenge_completion(user_challenge):
    """
    Check if a challenge is complete and award badge if so.

    Returns True if challenge was just completed.
    """
    from django.db.models import F
    from .models import Challenge, ChallengeEntry
    from apps.accounts.models import UserBadge

    challenge = user_challenge.challenge
    total_prompts = challenge.prompts.count()
    completed = ChallengeEntry.objects.filter(user_challenge=user_challenge).count()

    if completed >= total_prompts and user_challenge.status == 'active':
        # Mark as completed
        user_challenge.status = 'completed'
        user_challenge.completed_at = timezone.now()
        user_challenge.badge_earned = True
        user_challenge.badge_earned_at = timezone.now()
        user_challenge.save()

        # Award the badge
        UserBadge.objects.get_or_create(
            user=user_challenge.user,
            badge_id=challenge.badge_id,
            defaults={
                'streak_count': completed,
            }
        )

        # Update challenge completion count
        Challenge.objects.filter(pk=challenge.pk).update(
            completion_count=F('completion_count') + 1
        )

        return True

    return False
