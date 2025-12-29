"""
Signals for the Challenges app.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ChallengeEntry
from .services import update_challenge_progress, check_challenge_completion

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ChallengeEntry)
def handle_challenge_entry_created(sender, instance, created, **kwargs):
    """
    Handle when a new challenge entry is created.

    Updates progress and checks for completion.
    """
    if not created:
        return

    try:
        user_challenge = instance.user_challenge

        # Update progress counts
        update_challenge_progress(user_challenge)

        # Check if challenge is now complete
        completed = check_challenge_completion(user_challenge)

        if completed:
            logger.info(
                f"Challenge completed: {user_challenge.user.email} finished "
                f"'{user_challenge.challenge.title}' and earned badge '{user_challenge.challenge.badge_id}'"
            )

    except Exception as e:
        logger.error(f"Error handling challenge entry {instance.id}: {e}")
