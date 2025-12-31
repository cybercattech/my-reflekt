"""
Custom encrypted model fields that support per-user encryption keys.

These fields use the encryption key from thread-local storage (set by middleware).
If no key is available (e.g., manage.py shell), encrypted data is returned as-is.

During migration period: If no per-user key is available, falls back to global key
for users who haven't been migrated yet (encryption_version == 0).
"""
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

from .services.encryption import get_current_encryption_key


def get_global_key():
    """Get the global FERNET_ENCRYPTION_KEY for fallback."""
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if key:
        return key.encode() if isinstance(key, str) else key
    return None


class UserEncryptedTextField(models.TextField):
    """
    TextField that encrypts data using per-user encryption key.

    The encryption key is retrieved from thread-local storage, which is
    populated by the UserEncryptionMiddleware during authenticated requests.

    If no key is available:
    - On read: Returns raw encrypted data (gibberish)
    - On write: Raises ValueError (must be logged in to create/edit entries)
    """

    description = "A TextField that encrypts data with per-user keys"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Use custom path for migrations
        path = 'apps.journal.fields.UserEncryptedTextField'
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from database."""
        if value is None or value == '':
            return value

        # Try per-user key first
        key = get_current_encryption_key()

        if key:
            try:
                f = Fernet(key)
                decrypted = f.decrypt(value.encode('utf-8'))
                return decrypted.decode('utf-8')
            except InvalidToken:
                # Wrong key - maybe still encrypted with global key
                pass
            except Exception:
                pass

        # Fall back to global key (for unmigrated users)
        global_key = get_global_key()
        if global_key:
            try:
                f = Fernet(global_key)
                decrypted = f.decrypt(value.encode('utf-8'))
                return decrypted.decode('utf-8')
            except InvalidToken:
                # Not encrypted with global key either
                return value
            except Exception:
                return value

        # No keys available - return encrypted data as-is
        return value

    def get_prep_value(self, value):
        """Encrypt when saving to database."""
        if value is None or value == '':
            return value

        # Try per-user key first
        key = get_current_encryption_key()

        if key is None:
            # Fall back to global key (for unmigrated users)
            key = get_global_key()

        if key is None:
            # No key available - cannot encrypt
            raise ValueError(
                "Cannot save encrypted data: no encryption key available. "
                "User must be logged in to create or edit entries."
            )

        f = Fernet(key)
        encrypted = f.encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')

    def pre_save(self, model_instance, add):
        """
        Hook to access plaintext before encryption for analysis.

        This is critical for VADER sentiment analysis - we need the
        plaintext content before it gets encrypted.
        """
        value = getattr(model_instance, self.attname)

        # Store plaintext for post-save analysis
        # This will be accessed by signals before the model is saved
        if not hasattr(model_instance, '_plaintext_fields'):
            model_instance._plaintext_fields = {}
        model_instance._plaintext_fields[self.attname] = value

        return super().pre_save(model_instance, add)


class UserEncryptedCharField(UserEncryptedTextField):
    """
    CharField variant of UserEncryptedTextField.

    Note: Encrypted data is always longer than original, so this
    inherits from TextField for storage but can enforce max_length
    on the plaintext value.
    """

    description = "A CharField that encrypts data with per-user keys"

    def __init__(self, *args, max_length=None, **kwargs):
        self.max_length = max_length
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = 'apps.journal.fields.UserEncryptedCharField'
        if self.max_length is not None:
            kwargs['max_length'] = self.max_length
        return name, path, args, kwargs

    def get_prep_value(self, value):
        """Validate max_length before encryption."""
        if value and self.max_length and len(value) > self.max_length:
            raise ValueError(
                f"Value exceeds max_length ({self.max_length}): {len(value)} chars"
            )
        return super().get_prep_value(value)
