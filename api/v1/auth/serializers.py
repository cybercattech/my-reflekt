"""
Authentication serializers for the Reflekt API.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Profile


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with profile data."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'email', 'date_joined']


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user Profile."""
    user = UserSerializer(read_only=True)
    display_name = serializers.CharField(read_only=True)
    is_premium = serializers.BooleanField(read_only=True)
    zodiac_display = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'username', 'subscription_tier', 'timezone',
            'editor_preference', 'city', 'country_code', 'temperature_unit',
            'birthday', 'horoscope_enabled', 'devotion_enabled',
            'total_entries', 'current_streak', 'longest_streak', 'last_entry_date',
            'display_name', 'is_premium', 'zodiac_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'subscription_tier', 'total_entries', 'current_streak',
            'longest_streak', 'last_entry_date', 'created_at', 'updated_at'
        ]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer that uses email instead of username."""
    username_field = 'email'

    def validate(self, attrs):
        # Get email and password from request
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Find user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'detail': 'No account found with this email address.'
                })

            # Check if email is verified (allauth)
            if hasattr(user, 'emailaddress_set'):
                email_verified = user.emailaddress_set.filter(
                    email=email, verified=True
                ).exists()
                if not email_verified:
                    raise serializers.ValidationError({
                        'detail': 'Please verify your email address before logging in.'
                    })

            # Authenticate
            user = authenticate(
                request=self.context.get('request'),
                username=user.username,
                password=password
            )

            if not user:
                raise serializers.ValidationError({
                    'detail': 'Invalid email or password.'
                })

            if not user.is_active:
                raise serializers.ValidationError({
                    'detail': 'This account has been disabled.'
                })

        else:
            raise serializers.ValidationError({
                'detail': 'Email and password are required.'
            })

        # Get token
        refresh = self.get_token(user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserWithProfileSerializer(user).data
        }

        return data


class UserWithProfileSerializer(serializers.ModelSerializer):
    """User serializer with nested profile."""
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined', 'profile']
        read_only_fields = ['id', 'email', 'date_joined']


class SignupSerializer(serializers.Serializer):
    """Serializer for user registration."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=30)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate_email(self, value):
        """Ensure email is unique."""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(
                'An account with this email address already exists.'
            )
        return value.lower()

    def validate(self, attrs):
        """Ensure passwords match."""
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        return attrs

    def create(self, validated_data):
        """Create a new user."""
        validated_data.pop('password_confirm')
        email = validated_data.pop('email')

        user = User.objects.create_user(
            username=email,  # Use email as username
            email=email,
            password=validated_data.pop('password'),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password."""
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_old_password(self, value):
        """Verify old password is correct."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        """Ensure new passwords match."""
        if attrs.get('new_password') != attrs.get('new_password_confirm'):
            raise serializers.ValidationError({
                'new_password_confirm': 'Passwords do not match.'
            })
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=30)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=30)

    class Meta:
        model = Profile
        fields = [
            'username', 'timezone', 'editor_preference', 'city', 'country_code',
            'temperature_unit', 'birthday', 'horoscope_enabled', 'devotion_enabled',
            'first_name', 'last_name'
        ]

    def update(self, instance, validated_data):
        # Extract user fields
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)

        # Update user if needed
        if first_name is not None or last_name is not None:
            user = instance.user
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            user.save()

        # Update profile
        return super().update(instance, validated_data)
