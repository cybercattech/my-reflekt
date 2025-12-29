"""
Signal handlers for account-related events.

Note: Profile creation signals are in models.py.
This file contains additional friend/invitation signals.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def handle_new_user_invitations(sender, instance, created, **kwargs):
    """
    When a new user signs up, check for pending invitations.

    Updates Invitation.recipient and status to 'signed_up'
    so the new user can accept/deny from their settings.
    """
    if not created:
        return

    from .models import Invitation

    # Find pending invitations to this email
    pending_invitations = Invitation.objects.filter(
        email__iexact=instance.email,
        status='pending'
    )

    updated_count = 0
    for invitation in pending_invitations:
        if not invitation.is_expired:
            invitation.recipient = instance
            invitation.status = 'signed_up'
            invitation.save()
            updated_count += 1
            logger.info(
                f"Linked invitation from {invitation.sender.email} "
                f"to new user {instance.email}"
            )
        else:
            invitation.status = 'expired'
            invitation.save()

    if updated_count:
        logger.info(f"New user {instance.email} has {updated_count} pending invitation(s)")
