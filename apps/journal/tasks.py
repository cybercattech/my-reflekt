"""
Celery tasks for journal app.

Handles async email notifications for POV sharing.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def send_pov_notification(pov_id):
    """Send email notifications for a new POV to all recipients."""
    from .models import SharedPOV

    try:
        pov = SharedPOV.objects.select_related(
            'author', 'author__profile', 'entry'
        ).get(id=pov_id)
    except SharedPOV.DoesNotExist:
        logger.warning(f"SharedPOV {pov_id} not found")
        return f"SharedPOV {pov_id} not found"

    sent_count = 0
    for recipient in pov.recipients.select_related('user').filter(email_sent=False):
        if _send_pov_email(pov, recipient):
            sent_count += 1

    return f"Sent {sent_count} POV notifications"


@shared_task
def send_pov_notification_to_user(pov_id, user_id):
    """Send POV notification to a specific user."""
    from .models import SharedPOV, SharedPOVRecipient

    try:
        pov = SharedPOV.objects.select_related(
            'author', 'author__profile', 'entry'
        ).get(id=pov_id)
        recipient = pov.recipients.select_related('user').get(user_id=user_id)
    except (SharedPOV.DoesNotExist, SharedPOVRecipient.DoesNotExist):
        logger.warning(f"POV {pov_id} or recipient user {user_id} not found")
        return "Not found"

    if _send_pov_email(pov, recipient):
        return "Sent"
    return "Failed"


def _send_pov_email(pov, recipient):
    """Send the actual POV notification email."""
    from django.utils import timezone

    # Build the view URL - point to journal entry for that date
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    entry_date_str = pov.entry.entry_date.isoformat()
    view_url = f"{site_url}/journal/?date={entry_date_str}"

    context = {
        'author_name': pov.author.profile.display_name,
        'entry_date': pov.entry.entry_date,
        'pov_preview': pov.content[:200] + '...' if len(pov.content) > 200 else pov.content,
        'view_url': view_url,
        'site_url': site_url,
    }

    try:
        html_message = render_to_string('journal/emails/pov_shared.html', context)
        plain_message = render_to_string('journal/emails/pov_shared.txt', context)

        send_mail(
            subject=f"{pov.author.profile.display_name} shared a journal note with you",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.user.email],
            fail_silently=False,
        )

        recipient.email_sent = True
        recipient.email_sent_at = timezone.now()
        recipient.save(update_fields=['email_sent', 'email_sent_at'])

        logger.info(f"Sent POV notification to {recipient.user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send POV notification to {recipient.user.email}: {e}")
        return False


@shared_task
def send_pov_reply_notification(reply_id):
    """Send notification when someone replies to a POV."""
    from .models import POVReply

    try:
        reply = POVReply.objects.select_related(
            'pov', 'pov__author', 'pov__author__profile',
            'author', 'author__profile'
        ).get(id=reply_id)
    except POVReply.DoesNotExist:
        logger.warning(f"POVReply {reply_id} not found")
        return f"POVReply {reply_id} not found"

    # Notify author and all recipients except the replier
    notify_users = []

    if reply.author != reply.pov.author:
        notify_users.append(reply.pov.author)

    for recipient in reply.pov.recipients.select_related('user').exclude(user=reply.author):
        notify_users.append(recipient.user)

    sent_count = 0
    for user in notify_users:
        if _send_reply_email(reply, user):
            sent_count += 1

    return f"Sent {sent_count} reply notifications"


def _send_reply_email(reply, user):
    """Send reply notification email."""
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    view_url = f"{site_url}/journal/shared/{reply.pov.id}/"

    context = {
        'replier_name': reply.author.profile.display_name,
        'reply_preview': reply.content[:200] + '...' if len(reply.content) > 200 else reply.content,
        'view_url': view_url,
        'site_url': site_url,
    }

    try:
        html_message = render_to_string('journal/emails/pov_reply.html', context)
        plain_message = render_to_string('journal/emails/pov_reply.txt', context)

        send_mail(
            subject=f"{reply.author.profile.display_name} replied to a shared note",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Sent POV reply notification to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send POV reply notification to {user.email}: {e}")
        return False
