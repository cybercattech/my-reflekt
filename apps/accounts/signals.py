"""
Signal handlers for account-related events.

Note: Profile creation signals are in models.py.
This file contains additional friend/invitation signals.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings

from allauth.account.signals import user_logged_in, password_changed, password_set

logger = logging.getLogger(__name__)


# =============================================================================
# Per-User Encryption Signal Handlers
# =============================================================================

@receiver(user_logged_in)
def cache_encryption_key_on_login(sender, request, user, **kwargs):
    """
    After successful login, derive and cache the user's encryption key.

    If user hasn't been migrated to per-user encryption yet, migrate them.
    """
    from apps.journal.services.encryption import UserEncryptionService

    password = request.POST.get('password')
    if not password:
        # Password not in POST (e.g., social login) - skip encryption setup
        logger.debug(f"No password in login request for {user.email}, skipping encryption cache")
        return

    try:
        profile = user.profile
        service = UserEncryptionService(user, request.session)

        if profile.encryption_version == 0:
            # User needs migration from global key
            global_key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
            if global_key:
                logger.info(f"Migrating {user.email} from global to per-user encryption")
                migrated = service.migrate_from_global_key(password, global_key)
                logger.info(f"Migrated {migrated} entries for {user.email}")

                # Generate recovery key for user
                recovery_key = service.generate_recovery_key()

                # Store recovery key in session to show on next page
                request.session['show_recovery_key'] = recovery_key
                request.session['first_per_user_login'] = True
            else:
                # No global key - initialize fresh encryption
                logger.info(f"Initializing per-user encryption for {user.email}")
                service.initialize_encryption(password)
                recovery_key = service.generate_recovery_key()
                request.session['show_recovery_key'] = recovery_key
                request.session['first_per_user_login'] = True
        else:
            # Already migrated - just derive and cache key
            key = service.derive_key(password)
            service.cache_key_in_session(key)

    except Exception as e:
        logger.error(f"Error setting up encryption for {user.email}: {e}")


@receiver(password_changed)
def reencrypt_entries_on_password_change(sender, request, user, **kwargs):
    """
    Re-encrypt all entries when password is changed.

    This is critical - the encryption key is derived from the password,
    so changing the password requires re-encrypting all entries.
    """
    from apps.journal.services.encryption import UserEncryptionService

    old_password = request.POST.get('oldpassword')
    new_password = request.POST.get('password1')

    if not old_password or not new_password:
        logger.warning(f"Password change for {user.email} missing old/new password")
        return

    try:
        service = UserEncryptionService(user, request.session)

        # Only rotate if user has per-user encryption
        if user.profile.encryption_version > 0:
            logger.info(f"Rotating encryption key for {user.email}")
            service.rotate_key(old_password, new_password)
            logger.info(f"Successfully rotated encryption key for {user.email}")

    except Exception as e:
        logger.error(f"Error rotating encryption key for {user.email}: {e}")


@receiver(password_set)
def handle_password_set(sender, request, user, **kwargs):
    """
    Handle password being set (usually after signup or password reset).

    For new users, this initializes encryption.
    For password reset, we need the recovery key to re-encrypt entries.
    """
    from apps.journal.services.encryption import UserEncryptionService

    new_password = request.POST.get('password1')
    recovery_key = request.POST.get('recovery_key')

    if not new_password:
        return

    try:
        profile = user.profile
        service = UserEncryptionService(user, request.session)

        if profile.encryption_version == 0:
            # New user - initialize encryption
            logger.info(f"Initializing encryption for new user {user.email}")
            service.initialize_encryption(new_password)
            recovery_key_generated = service.generate_recovery_key()
            request.session['show_recovery_key'] = recovery_key_generated
            request.session['first_per_user_login'] = True

        elif recovery_key and service.verify_recovery_key(recovery_key):
            # Password reset with valid recovery key
            # Note: This requires old key which we don't have
            # We can only re-initialize, losing old entries
            logger.warning(f"Password reset for {user.email} - entries need re-encryption")
            # For now, just cache the new key
            key = service.derive_key(new_password)
            service.cache_key_in_session(key)

    except Exception as e:
        logger.error(f"Error handling password set for {user.email}: {e}")


@receiver(post_save, sender=User)
def send_welcome_email_on_signup(sender, instance, created, **kwargs):
    """
    Send welcome email when a new user signs up.
    """
    if not created:
        return

    # Delay import to avoid circular imports
    from .subscription_emails import send_welcome_email

    try:
        send_welcome_email(instance)
    except Exception as e:
        logger.error(f"Failed to send welcome email to {instance.email}: {e}")


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
