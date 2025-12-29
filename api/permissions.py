"""
Custom permissions for the Reflekt API.
"""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    def has_object_permission(self, request, view, obj):
        # Check if object has a 'user' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # Check if object has an 'owner' attribute
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Read permissions are allowed for any authenticated request.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        return False


class IsPremiumUser(permissions.BasePermission):
    """
    Permission check for premium features.
    """
    message = 'This feature requires a premium subscription.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Check if user has premium subscription
        profile = getattr(request.user, 'profile', None)
        if profile:
            return profile.subscription_tier == 'premium'
        return False
