"""
Middleware to inject user's encryption key into thread-local storage.

This allows encrypted model fields to access the key without passing it
through every function call.
"""
from django.utils.deprecation import MiddlewareMixin

from .services.encryption import (
    set_current_encryption_key,
    clear_current_encryption_key,
    UserEncryptionService,
)


class UserEncryptionMiddleware(MiddlewareMixin):
    """
    Middleware that loads user's encryption key into thread-local storage.

    The key is loaded from the session (where it's stored after login).
    This makes the key available to encrypted model fields during the request.

    At the end of the request, the key is cleared from thread-local storage.
    """

    def process_request(self, request):
        """Load encryption key into thread-local at request start."""
        if request.user.is_authenticated:
            try:
                service = UserEncryptionService(request.user, request.session)
                key = service.get_cached_key()
                if key:
                    set_current_encryption_key(key)
            except Exception:
                # Don't break the request if encryption setup fails
                pass

    def process_response(self, request, response):
        """Clear encryption key from thread-local at request end."""
        clear_current_encryption_key()
        return response

    def process_exception(self, request, exception):
        """Clear encryption key even if exception occurs."""
        clear_current_encryption_key()
        return None
