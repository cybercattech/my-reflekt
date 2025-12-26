"""
Template tags for subscription tier checks.
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def is_premium(context):
    """Check if current user has premium subscription."""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    return request.user.profile.is_premium


@register.simple_tag(takes_context=True)
def is_free(context):
    """Check if current user is on free tier."""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return True
    return request.user.profile.is_free


@register.filter
def user_is_premium(user):
    """Filter to check if a user object has premium subscription."""
    if not user or not user.is_authenticated:
        return False
    return user.profile.is_premium


@register.filter
def user_is_free(user):
    """Filter to check if a user object is on free tier."""
    if not user or not user.is_authenticated:
        return True
    return user.profile.is_free
