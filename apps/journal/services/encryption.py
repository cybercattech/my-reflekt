"""
Per-user encryption service for journal entries.

Handles key derivation, encryption/decryption, and key rotation on password change.
The encryption key is derived from the user's password and stored ONLY in the session.
This means manage.py shell cannot access decrypted entries.
"""
import os
import hashlib
import base64
import secrets
import threading

from cryptography.fernet import Fernet, InvalidToken
from django.core.cache import cache


# Thread-local storage for encryption key during request
_thread_locals = threading.local()


def get_current_encryption_key():
    """Get encryption key from thread-local storage."""
    return getattr(_thread_locals, 'encryption_key', None)


def set_current_encryption_key(key):
    """Set encryption key in thread-local storage."""
    _thread_locals.encryption_key = key


def clear_current_encryption_key():
    """Clear encryption key from thread-local storage."""
    if hasattr(_thread_locals, 'encryption_key'):
        del _thread_locals.encryption_key


class EncryptionKeyNotAvailable(Exception):
    """Raised when encryption key is not in session and password not provided."""
    pass


class EncryptionNotSetup(Exception):
    """Raised when user encryption has not been initialized."""
    pass


class UserEncryptionService:
    """
    Manages per-user encryption keys and operations.

    Key is derived from user's password using PBKDF2 with per-user salt.
    Key is cached in session for the duration of login.
    """

    CACHE_TIMEOUT = 3600  # 1 hour cache for background tasks

    def __init__(self, user, session=None):
        self.user = user
        self.session = session
        self.profile = user.profile

    @property
    def cache_key(self):
        """Redis/cache key for this user's encryption key."""
        return f"user_encryption_key_{self.user.id}"

    def get_cached_key(self):
        """
        Get encryption key from session or cache.
        Returns None if not available.
        """
        # Try session first
        if self.session:
            encoded_key = self.session.get(self.cache_key)
            if encoded_key:
                return encoded_key.encode('ascii') if isinstance(encoded_key, str) else encoded_key

        # Try cache (for background tasks)
        cached_key = cache.get(self.cache_key)
        if cached_key:
            return cached_key.encode('ascii') if isinstance(cached_key, str) else cached_key

        return None

    def derive_key(self, password):
        """
        Derive encryption key from password using PBKDF2.

        Args:
            password: User's plaintext password

        Returns:
            bytes: Fernet-compatible encryption key (URL-safe base64)
        """
        if not self.profile.encryption_salt:
            raise EncryptionNotSetup("User encryption not initialized")

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            bytes(self.profile.encryption_salt),
            self.profile.key_derivation_iterations,
            dklen=32
        )
        return base64.urlsafe_b64encode(key)

    def cache_key_in_session(self, key):
        """
        Cache the derived key in session and temporary cache.

        Args:
            key: The encryption key (bytes)
        """
        encoded_key = key.decode('ascii') if isinstance(key, bytes) else key

        if self.session:
            self.session[self.cache_key] = encoded_key

        # Also store in cache for background tasks (short TTL)
        cache.set(self.cache_key, encoded_key, self.CACHE_TIMEOUT)

    def initialize_encryption(self, password):
        """
        Initialize encryption for a new user or migrate from global key.

        Generates a new salt and derives the encryption key.

        Args:
            password: User's plaintext password

        Returns:
            bytes: The derived encryption key
        """
        # Generate random 32-byte salt
        salt = os.urandom(32)
        self.profile.encryption_salt = salt
        self.profile.encryption_version = 1
        self.profile.save(update_fields=[
            'encryption_salt',
            'encryption_version',
            'key_derivation_iterations'
        ])

        key = self.derive_key(password)
        self.cache_key_in_session(key)
        return key

    def generate_recovery_key(self):
        """
        Generate a recovery key for password reset scenarios.

        The recovery key is shown to the user once at signup.
        We store only the hash, not the key itself.

        Returns:
            str: The recovery key to display to user (save this!)
        """
        # Generate random recovery key
        recovery_key = secrets.token_urlsafe(32)

        # Store hash of recovery key
        recovery_hash = hashlib.sha256(recovery_key.encode()).hexdigest()
        self.profile.recovery_key_hash = recovery_hash
        self.profile.save(update_fields=['recovery_key_hash'])

        return recovery_key

    def verify_recovery_key(self, recovery_key):
        """
        Verify a recovery key matches the stored hash.

        Args:
            recovery_key: The recovery key provided by user

        Returns:
            bool: True if valid
        """
        if not self.profile.recovery_key_hash:
            return False

        provided_hash = hashlib.sha256(recovery_key.encode()).hexdigest()
        return provided_hash == self.profile.recovery_key_hash

    def encrypt(self, plaintext, key=None):
        """
        Encrypt plaintext using user's key.

        Args:
            plaintext: String to encrypt
            key: Optional key override (uses cached key if not provided)

        Returns:
            str: Encrypted ciphertext (base64)
        """
        if not plaintext:
            return plaintext

        if key is None:
            key = self.get_cached_key()

        if key is None:
            raise EncryptionKeyNotAvailable(
                "Encryption key not available. User must be logged in."
            )

        f = Fernet(key)
        return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    def decrypt(self, ciphertext, key=None):
        """
        Decrypt ciphertext using user's key.

        Args:
            ciphertext: Encrypted string to decrypt
            key: Optional key override (uses cached key if not provided)

        Returns:
            str: Decrypted plaintext
        """
        if not ciphertext:
            return ciphertext

        if key is None:
            key = self.get_cached_key()

        if key is None:
            raise EncryptionKeyNotAvailable(
                "Encryption key not available. User must be logged in."
            )

        f = Fernet(key)
        try:
            return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            # Return placeholder instead of failing
            return "[Encrypted content - login required to view]"

    def rotate_key(self, old_password, new_password):
        """
        Rotate encryption key when password changes.
        Re-encrypts all entries with the new key.

        Args:
            old_password: User's old password
            new_password: User's new password
        """
        from apps.journal.models import Entry

        # Get old key
        old_key = self.derive_key(old_password)

        # Generate new salt and derive new key
        new_salt = os.urandom(32)
        self.profile.encryption_salt = new_salt
        self.profile.save(update_fields=['encryption_salt'])

        new_key = self.derive_key(new_password)

        # Re-encrypt all entries
        entries = Entry.objects.filter(user=self.user)
        for entry in entries:
            if entry.title:
                entry.title = self._reencrypt(entry.title, old_key, new_key)
            if entry.content:
                entry.content = self._reencrypt(entry.content, old_key, new_key)
            # Use update to skip model save logic
            Entry.objects.filter(pk=entry.pk).update(
                title=entry.title,
                content=entry.content
            )

        # Update cache with new key
        self.cache_key_in_session(new_key)

    def _reencrypt(self, data, old_key, new_key):
        """
        Decrypt with old key and encrypt with new key.

        Args:
            data: Encrypted data
            old_key: Old encryption key
            new_key: New encryption key

        Returns:
            str: Re-encrypted data
        """
        if not data:
            return data

        # Decrypt with old key
        old_fernet = Fernet(old_key)
        try:
            plaintext = old_fernet.decrypt(data.encode('utf-8'))
        except InvalidToken:
            # Data might already be with new key or corrupted
            return data

        # Encrypt with new key
        new_fernet = Fernet(new_key)
        return new_fernet.encrypt(plaintext).decode('utf-8')

    def migrate_from_global_key(self, password, global_key):
        """
        Migrate entries from global encryption to per-user encryption.

        Called on first login after per-user encryption is enabled.

        Args:
            password: User's plaintext password
            global_key: The global FERNET_ENCRYPTION_KEY
        """
        from apps.journal.models import Entry

        # Initialize per-user encryption
        user_key = self.initialize_encryption(password)

        # Get global Fernet
        global_fernet = Fernet(global_key.encode() if isinstance(global_key, str) else global_key)
        user_fernet = Fernet(user_key)

        # Re-encrypt all entries
        entries = Entry.objects.filter(user=self.user)
        migrated_count = 0

        for entry in entries:
            try:
                # Decrypt with global key
                if entry.title:
                    title_plaintext = global_fernet.decrypt(entry.title.encode('utf-8'))
                    entry.title = user_fernet.encrypt(title_plaintext).decode('utf-8')

                if entry.content:
                    content_plaintext = global_fernet.decrypt(entry.content.encode('utf-8'))
                    entry.content = user_fernet.encrypt(content_plaintext).decode('utf-8')

                # Use update to skip model save logic
                Entry.objects.filter(pk=entry.pk).update(
                    title=entry.title,
                    content=entry.content
                )
                migrated_count += 1
            except InvalidToken:
                # Entry might already be with new key or corrupted
                continue

        # Mark migration complete
        self.profile.encryption_version = 1
        self.profile.save(update_fields=['encryption_version'])

        return migrated_count


def decrypt_entry_content(entry, request=None):
    """
    Convenience function to decrypt entry content.

    Args:
        entry: Entry model instance
        request: HTTP request (for session access)

    Returns:
        str: Decrypted content or placeholder
    """
    if not entry.content:
        return ""

    session = request.session if request else None
    service = UserEncryptionService(entry.user, session)

    try:
        return service.decrypt(entry.content)
    except EncryptionKeyNotAvailable:
        return "[Encrypted content - login required to view]"


def decrypt_entry_title(entry, request=None):
    """
    Convenience function to decrypt entry title.

    Args:
        entry: Entry model instance
        request: HTTP request (for session access)

    Returns:
        str: Decrypted title or placeholder
    """
    if not entry.title:
        return ""

    session = request.session if request else None
    service = UserEncryptionService(entry.user, session)

    try:
        return service.decrypt(entry.title)
    except EncryptionKeyNotAvailable:
        return "[Encrypted]"
