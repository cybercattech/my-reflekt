"""
Friends views for the Reflekt API.
"""
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.accounts.models import Friendship, FriendRequest, Invitation, Profile
from api.pagination import StandardResultsPagination

from .serializers import (
    FriendSerializer, FriendRequestSerializer,
    FriendRequestCreateSerializer, FriendRequestResponseSerializer,
    UserSearchSerializer, InvitationSerializer, InvitationCreateSerializer
)


class FriendsListView(APIView):
    """
    List all friends of the current user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List friends",
        description="Get list of all friends for the current user."
    )
    def get(self, request):
        friends = Friendship.get_friends(request.user)

        # Get friendship dates
        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user)
        )
        friendship_dates = {}
        for f in friendships:
            friend = f.user2 if f.user1 == request.user else f.user1
            friendship_dates[friend.id] = f.created_at

        result = []
        for friend in friends:
            profile = getattr(friend, 'profile', None)
            result.append({
                'id': profile.id if profile else friend.id,
                'user_id': friend.id,
                'username': profile.username if profile else None,
                'email': friend.email,
                'first_name': friend.first_name,
                'last_name': friend.last_name,
                'display_name': profile.display_name if profile else friend.email,
                'current_streak': profile.current_streak if profile else 0,
                'friendship_date': friendship_dates.get(friend.id),
            })

        return Response(result)


class RemoveFriendView(APIView):
    """
    Remove a friend.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Remove friend",
        description="Remove a friend from your friends list."
    )
    def delete(self, request, user_id):
        try:
            friend = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not Friendship.are_friends(request.user, friend):
            return Response(
                {'error': 'You are not friends with this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delete the friendship
        user1, user2 = (request.user, friend) if request.user.id < friend.id else (friend, request.user)
        Friendship.objects.filter(user1=user1, user2=user2).delete()

        return Response({'message': 'Friend removed.'})


class FriendRequestsReceivedView(generics.ListAPIView):
    """
    List pending friend requests received.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    @extend_schema(summary="List received friend requests")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return FriendRequest.objects.filter(
            recipient=self.request.user,
            status='pending'
        ).select_related('sender', 'recipient')


class FriendRequestsSentView(generics.ListAPIView):
    """
    List pending friend requests sent.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    @extend_schema(summary="List sent friend requests")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return FriendRequest.objects.filter(
            sender=self.request.user,
            status='pending'
        ).select_related('sender', 'recipient')


class SendFriendRequestView(APIView):
    """
    Send a friend request.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send friend request",
        request=FriendRequestCreateSerializer
    )
    def post(self, request):
        serializer = FriendRequestCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        recipient = serializer.validated_data['recipient']
        message = serializer.validated_data.get('message', '')

        friend_request = FriendRequest.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message
        )

        # Send friend request notification email
        try:
            from apps.accounts.tasks import send_friend_request_email
            send_friend_request_email.delay(friend_request.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not queue friend request email: {e}")

        return Response(
            FriendRequestSerializer(friend_request).data,
            status=status.HTTP_201_CREATED
        )


class RespondToFriendRequestView(APIView):
    """
    Accept or decline a friend request.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Respond to friend request",
        request=FriendRequestResponseSerializer
    )
    def post(self, request, pk):
        try:
            friend_request = FriendRequest.objects.get(
                id=pk,
                recipient=request.user,
                status='pending'
            )
        except FriendRequest.DoesNotExist:
            return Response(
                {'error': 'Friend request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = FriendRequestResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        accept = serializer.validated_data['accept']

        if accept:
            # Create friendship
            Friendship.create_friendship(request.user, friend_request.sender)
            friend_request.status = 'accepted'
            message = 'Friend request accepted.'
        else:
            friend_request.status = 'denied'
            message = 'Friend request declined.'

        friend_request.responded_at = timezone.now()
        friend_request.save()

        return Response({'message': message})


class CancelFriendRequestView(APIView):
    """
    Cancel a sent friend request.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Cancel friend request")
    def delete(self, request, pk):
        try:
            friend_request = FriendRequest.objects.get(
                id=pk,
                sender=request.user,
                status='pending'
            )
        except FriendRequest.DoesNotExist:
            return Response(
                {'error': 'Friend request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        friend_request.status = 'cancelled'
        friend_request.responded_at = timezone.now()
        friend_request.save()

        return Response({'message': 'Friend request cancelled.'})


class UserSearchView(APIView):
    """
    Search for users by username or email.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search users",
        parameters=[
            OpenApiParameter(name='q', description='Search query', required=True),
        ]
    )
    def get(self, request):
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response(
                {'error': 'Query must be at least 2 characters.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Search by username or email
        users = User.objects.filter(
            Q(profile__username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id).select_related('profile')[:20]

        # Get pending requests
        pending_sent = set(FriendRequest.objects.filter(
            sender=request.user,
            status='pending'
        ).values_list('recipient_id', flat=True))

        pending_received = set(FriendRequest.objects.filter(
            recipient=request.user,
            status='pending'
        ).values_list('sender_id', flat=True))

        pending_requests = pending_sent | pending_received

        result = []
        for user in users:
            profile = getattr(user, 'profile', None)
            result.append({
                'id': user.id,
                'username': profile.username if profile else None,
                'email': user.email,
                'display_name': profile.display_name if profile else user.email,
                'is_friend': Friendship.are_friends(request.user, user),
                'has_pending_request': user.id in pending_requests,
            })

        return Response(result)


class InvitationsListView(generics.ListAPIView):
    """
    List invitations sent by the current user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = InvitationSerializer
    pagination_class = StandardResultsPagination

    @extend_schema(summary="List sent invitations")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Invitation.objects.filter(sender=self.request.user)


class SendInvitationView(APIView):
    """
    Send an invitation to someone not on the platform.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send invitation",
        request=InvitationCreateSerializer
    )
    def post(self, request):
        serializer = InvitationCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        invitation = Invitation.objects.create(
            sender=request.user,
            email=serializer.validated_data['email'],
            message=serializer.validated_data.get('message', '')
        )

        # Send invitation email
        try:
            from apps.accounts.tasks import send_invitation_email
            send_invitation_email.delay(invitation.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not queue invitation email: {e}")

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED
        )
