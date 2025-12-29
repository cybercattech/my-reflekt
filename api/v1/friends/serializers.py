"""
Friends serializers for the Reflekt API.
"""
from django.contrib.auth.models import User
from rest_framework import serializers
from apps.accounts.models import Friendship, FriendRequest, Invitation, Profile


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile in friend context."""
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'display_name', 'current_streak', 'total_entries'
        ]


class FriendSerializer(serializers.Serializer):
    """Serializer for friend list items."""
    id = serializers.IntegerField(source='profile.id')
    user_id = serializers.IntegerField(source='id')
    username = serializers.CharField(source='profile.username', allow_null=True)
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    display_name = serializers.CharField(source='profile.display_name')
    current_streak = serializers.IntegerField(source='profile.current_streak')
    friendship_date = serializers.DateTimeField(allow_null=True)


class FriendRequestSerializer(serializers.ModelSerializer):
    """Serializer for friend requests."""
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    sender_username = serializers.SerializerMethodField()
    sender_display_name = serializers.SerializerMethodField()
    recipient_email = serializers.CharField(source='recipient.email', read_only=True)
    recipient_username = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = [
            'id', 'sender_email', 'sender_username', 'sender_display_name',
            'recipient_email', 'recipient_username',
            'status', 'message', 'created_at', 'responded_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'responded_at']

    def get_sender_username(self, obj):
        profile = getattr(obj.sender, 'profile', None)
        return profile.username if profile else None

    def get_sender_display_name(self, obj):
        profile = getattr(obj.sender, 'profile', None)
        return profile.display_name if profile else obj.sender.email

    def get_recipient_username(self, obj):
        profile = getattr(obj.recipient, 'profile', None)
        return profile.username if profile else None


class FriendRequestCreateSerializer(serializers.Serializer):
    """Serializer for creating friend requests."""
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs):
        username = attrs.get('username', '').strip()
        email = attrs.get('email', '').strip()

        if not username and not email:
            raise serializers.ValidationError(
                'Either username or email is required.'
            )

        # Find the recipient
        recipient = None

        if username:
            profile = Profile.objects.filter(username__iexact=username).first()
            if profile:
                recipient = profile.user

        if not recipient and email:
            recipient = User.objects.filter(email__iexact=email).first()

        if not recipient:
            raise serializers.ValidationError(
                'User not found. Check the username or email.'
            )

        # Check if it's self
        request = self.context.get('request')
        if recipient == request.user:
            raise serializers.ValidationError(
                "You can't send a friend request to yourself."
            )

        # Check if already friends
        if Friendship.are_friends(request.user, recipient):
            raise serializers.ValidationError(
                'You are already friends with this user.'
            )

        # Check if request already exists
        existing = FriendRequest.objects.filter(
            sender=request.user,
            recipient=recipient,
            status='pending'
        ).exists()
        if existing:
            raise serializers.ValidationError(
                'A pending friend request already exists.'
            )

        # Check reverse request
        reverse = FriendRequest.objects.filter(
            sender=recipient,
            recipient=request.user,
            status='pending'
        ).exists()
        if reverse:
            raise serializers.ValidationError(
                'This user has already sent you a friend request. Check your pending requests.'
            )

        attrs['recipient'] = recipient
        return attrs


class FriendRequestResponseSerializer(serializers.Serializer):
    """Serializer for responding to friend requests."""
    accept = serializers.BooleanField(required=True)


class UserSearchSerializer(serializers.Serializer):
    """Serializer for user search results."""
    id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True)
    email = serializers.EmailField()
    display_name = serializers.CharField()
    is_friend = serializers.BooleanField()
    has_pending_request = serializers.BooleanField()


class InvitationSerializer(serializers.ModelSerializer):
    """Serializer for invitations."""

    class Meta:
        model = Invitation
        fields = [
            'id', 'email', 'status', 'message',
            'email_sent_at', 'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'status', 'email_sent_at', 'created_at', 'expires_at']


class InvitationCreateSerializer(serializers.Serializer):
    """Serializer for creating invitations."""
    email = serializers.EmailField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_email(self, value):
        email = value.lower()

        # Check if user already exists
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                'This person already has an account. Send them a friend request instead.'
            )

        # Check if invitation already sent
        request = self.context.get('request')
        if Invitation.objects.filter(sender=request.user, email__iexact=email).exists():
            raise serializers.ValidationError(
                'You have already invited this person.'
            )

        return email
