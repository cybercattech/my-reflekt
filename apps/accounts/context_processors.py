"""
Context processors for accounts app.

These functions add variables to all template contexts.
"""


def pending_friend_requests(request):
    """
    Add pending friend request count to all templates for authenticated users.
    """
    if not request.user.is_authenticated:
        return {}

    from .models import FriendRequest

    pending_requests = FriendRequest.objects.filter(
        recipient=request.user,
        status='pending'
    ).select_related('sender', 'sender__profile')

    return {
        'pending_friend_requests': pending_requests,
        'pending_friend_requests_count': pending_requests.count(),
    }
