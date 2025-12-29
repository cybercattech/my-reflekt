"""
Email functions for subscription-related notifications.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def get_site_url():
    """Get the site URL from settings."""
    return getattr(settings, 'SITE_URL', 'https://myreflekt.net')


def send_welcome_email(user):
    """
    Send welcome email to new users (first-time signup).
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/welcome.html', context)
    plain_message = render_to_string('accounts/emails/subscription/welcome.txt', context)

    try:
        send_mail(
            subject="Welcome to Reflekt! Your journaling journey begins",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")
        return False


def send_trial_started_email(user, trial_end_date):
    """
    Send email when user starts their premium trial.
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'trial_end_date': trial_end_date,
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/trial_started.html', context)
    plain_message = render_to_string('accounts/emails/subscription/trial_started.txt', context)

    try:
        send_mail(
            subject="Your 14-day Premium trial has started!",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Trial started email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send trial started email to {user.email}: {e}")
        return False


def send_trial_ending_reminder_email(user, days_remaining, trial_end_date):
    """
    Send reminder email when trial is about to end.
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'days_remaining': days_remaining,
        'trial_end_date': trial_end_date,
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/trial_ending.html', context)
    plain_message = render_to_string('accounts/emails/subscription/trial_ending.txt', context)

    try:
        send_mail(
            subject=f"Your Reflekt trial ends in {days_remaining} days",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Trial ending reminder sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send trial ending reminder to {user.email}: {e}")
        return False


def send_payment_reminder_email(user, charge_date, amount, plan_name):
    """
    Send reminder email the day before card is charged.
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'charge_date': charge_date,
        'amount': amount,
        'plan_name': plan_name,
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/payment_reminder.html', context)
    plain_message = render_to_string('accounts/emails/subscription/payment_reminder.txt', context)

    try:
        send_mail(
            subject="Your Reflekt subscription renews tomorrow",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Payment reminder sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send payment reminder to {user.email}: {e}")
        return False


def send_payment_success_email(user, amount, plan_name, next_billing_date):
    """
    Send thank you email after successful payment.
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'amount': amount,
        'plan_name': plan_name,
        'next_billing_date': next_billing_date,
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/payment_success.html', context)
    plain_message = render_to_string('accounts/emails/subscription/payment_success.txt', context)

    try:
        send_mail(
            subject="Thank you for your Reflekt subscription!",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Payment success email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send payment success email to {user.email}: {e}")
        return False


def send_payment_failed_email(user):
    """
    Send email when payment fails and user is downgraded.
    """
    context = {
        'user_name': user.profile.display_name or user.email.split('@')[0],
        'site_url': get_site_url(),
    }

    html_message = render_to_string('accounts/emails/subscription/payment_failed.html', context)
    plain_message = render_to_string('accounts/emails/subscription/payment_failed.txt', context)

    try:
        send_mail(
            subject="Action required: Your Reflekt payment failed",
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Payment failed email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send payment failed email to {user.email}: {e}")
        return False


# =============================================================================
# Admin Notification Emails
# =============================================================================

ADMIN_EMAIL = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', 'fetter@zoho.com')


def send_admin_new_subscriber_notification(user, plan_name, subscription_status, has_payment_method=True):
    """
    Send notification to admin when someone subscribes.

    Args:
        user: The user who subscribed
        plan_name: Name of the plan they selected (e.g., "Individual Monthly")
        subscription_status: Status from Stripe ("trialing" or "active")
        has_payment_method: Whether they entered payment info
    """
    is_trial = subscription_status == 'trialing'

    subject = f"[Reflekt] New Subscriber: {user.email}"

    message = f"""
New Subscription on Reflekt!

User: {user.email}
Name: {user.profile.display_name or 'Not set'}
Plan: {plan_name}
Status: {'14-Day Trial' if is_trial else 'Active (Paid)'}
Payment Method: {'Yes' if has_payment_method else 'No'}
Signed Up: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

---
View in Admin: {get_site_url()}/accounts/manage/users/{user.id}/
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ADMIN_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Admin notification sent for new subscriber: {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin notification for {user.email}: {e}")
        return False


def send_admin_subscription_cancelled_notification(user, plan_name):
    """
    Send notification to admin when someone cancels their subscription.
    """
    subject = f"[Reflekt] Subscription Cancelled: {user.email}"

    message = f"""
Subscription Cancelled on Reflekt

User: {user.email}
Name: {user.profile.display_name or 'Not set'}
Previous Plan: {plan_name}
Cancelled: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

---
View in Admin: {get_site_url()}/accounts/manage/users/{user.id}/
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ADMIN_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Admin notification sent for cancelled subscription: {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin cancellation notification for {user.email}: {e}")
        return False
