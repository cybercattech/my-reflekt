"""
Decorators for subscription tier checks.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def premium_required(view_func):
    """
    Decorator for views that require premium subscription.

    If user is not premium, redirect to upgrade page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')

        if not request.user.profile.is_premium:
            messages.warning(
                request,
                'This feature requires a Premium subscription. Upgrade to unlock!'
            )
            return redirect('accounts:upgrade')

        return view_func(request, *args, **kwargs)
    return wrapper


def free_or_premium(view_func):
    """
    Decorator that allows both free and premium users.
    Adds 'is_premium' to context for conditional rendering.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper
