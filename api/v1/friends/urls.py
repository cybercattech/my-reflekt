"""
Friends URL patterns for the Reflekt API.
"""
from django.urls import path

from .views import (
    FriendsListView, RemoveFriendView,
    FriendRequestsReceivedView, FriendRequestsSentView,
    SendFriendRequestView, RespondToFriendRequestView, CancelFriendRequestView,
    UserSearchView, InvitationsListView, SendInvitationView
)

urlpatterns = [
    # Friends
    path('', FriendsListView.as_view(), name='friends_list'),
    path('<int:user_id>/', RemoveFriendView.as_view(), name='remove_friend'),

    # Friend requests
    path('requests/received/', FriendRequestsReceivedView.as_view(), name='requests_received'),
    path('requests/sent/', FriendRequestsSentView.as_view(), name='requests_sent'),
    path('requests/send/', SendFriendRequestView.as_view(), name='send_request'),
    path('requests/<int:pk>/respond/', RespondToFriendRequestView.as_view(), name='respond_request'),
    path('requests/<int:pk>/cancel/', CancelFriendRequestView.as_view(), name='cancel_request'),

    # User search
    path('search/', UserSearchView.as_view(), name='user_search'),

    # Invitations
    path('invitations/', InvitationsListView.as_view(), name='invitations_list'),
    path('invitations/send/', SendInvitationView.as_view(), name='send_invitation'),
]
