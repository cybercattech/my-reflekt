"""
Celery tasks for friend-related email notifications.
"""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_friend_request_email(request_id):
    """
    Send email notification for new friend request.
    """
    from .models import FriendRequest

    try:
        request = FriendRequest.objects.select_related(
            'sender', 'sender__profile', 'recipient'
        ).get(id=request_id)
    except FriendRequest.DoesNotExist:
        return f"FriendRequest {request_id} not found"

    sender_name = request.sender.profile.display_name

    context = {
        'sender_name': sender_name,
        'sender_email': request.sender.email,
        'message': request.message,
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }

    html_message = render_to_string('accounts/emails/friend_request.html', context)
    plain_message = render_to_string('accounts/emails/friend_request.txt', context)

    send_mail(
        subject=f"{sender_name} wants to be your friend on Reflekt",
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.recipient.email],
        fail_silently=False,
    )

    logger.info(f"Friend request email sent to {request.recipient.email}")
    return f"Email sent to {request.recipient.email}"


@shared_task
def send_friend_request_accepted_email(request_id):
    """
    Notify sender that their friend request was accepted.
    """
    from .models import FriendRequest

    try:
        request = FriendRequest.objects.select_related(
            'sender', 'recipient', 'recipient__profile'
        ).get(id=request_id)
    except FriendRequest.DoesNotExist:
        return f"FriendRequest {request_id} not found"

    accepter_name = request.recipient.profile.display_name

    context = {
        'accepter_name': accepter_name,
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }

    html_message = render_to_string('accounts/emails/friend_request_accepted.html', context)
    plain_message = render_to_string('accounts/emails/friend_request_accepted.txt', context)

    send_mail(
        subject=f"{accepter_name} accepted your friend request on Reflekt",
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.sender.email],
        fail_silently=False,
    )

    logger.info(f"Acceptance email sent to {request.sender.email}")
    return f"Email sent to {request.sender.email}"


@shared_task
def send_invitation_email(invitation_id):
    """
    Send invitation email to non-user.
    """
    from .models import Invitation

    try:
        invitation = Invitation.objects.select_related(
            'sender', 'sender__profile'
        ).get(id=invitation_id)
    except Invitation.DoesNotExist:
        return f"Invitation {invitation_id} not found"

    sender_name = invitation.sender.profile.display_name

    context = {
        'sender_name': sender_name,
        'sender_email': invitation.sender.email,
        'message': invitation.message,
        'signup_url': f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/accounts/signup/?invite={invitation.token}",
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }

    html_message = render_to_string('accounts/emails/invitation.html', context)
    plain_message = render_to_string('accounts/emails/invitation.txt', context)

    send_mail(
        subject=f"{sender_name} invited you to join Reflekt",
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )

    # Update email_sent_at
    invitation.email_sent_at = timezone.now()
    invitation.save(update_fields=['email_sent_at'])

    logger.info(f"Invitation email sent to {invitation.email}")
    return f"Email sent to {invitation.email}"


@shared_task
def send_invitation_accepted_email(invitation_id):
    """
    Notify inviter that invited person signed up and accepted.
    """
    from .models import Invitation

    try:
        invitation = Invitation.objects.select_related(
            'sender', 'recipient', 'recipient__profile'
        ).get(id=invitation_id)
    except Invitation.DoesNotExist:
        return f"Invitation {invitation_id} not found"

    new_friend_name = invitation.recipient.profile.display_name

    context = {
        'new_friend_name': new_friend_name,
        'new_friend_email': invitation.recipient.email,
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }

    html_message = render_to_string('accounts/emails/invitation_accepted.html', context)
    plain_message = render_to_string('accounts/emails/invitation_accepted.txt', context)

    send_mail(
        subject=f"{new_friend_name} joined Reflekt and is now your friend!",
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.sender.email],
        fail_silently=False,
    )

    logger.info(f"Invitation accepted email sent to {invitation.sender.email}")
    return f"Email sent to {invitation.sender.email}"
