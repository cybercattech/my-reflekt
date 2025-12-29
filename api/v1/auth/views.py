"""
Authentication views for the Reflekt API.
"""
from django.contrib.auth.models import User
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from drf_spectacular.utils import extend_schema, OpenApiExample

from .serializers import (
    CustomTokenObtainPairSerializer,
    SignupSerializer,
    UserWithProfileSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
)


class LoginView(TokenObtainPairView):
    """
    Login endpoint - obtain JWT access and refresh tokens.

    Returns tokens and user profile data.
    """
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="Login with email and password",
        description="Authenticate with email and password to receive JWT tokens.",
        examples=[
            OpenApiExample(
                'Login Request',
                value={
                    'email': 'user@example.com',
                    'password': 'securepassword'
                },
                request_only=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'access': {'type': 'string'},
                    'refresh': {'type': 'string'},
                    'user': {'type': 'object'}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SignupView(generics.CreateAPIView):
    """
    Register a new user account.

    Creates user and profile, returns tokens for immediate login.
    """
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    @extend_schema(
        summary="Create a new user account",
        description="Register with email and password. Returns JWT tokens for immediate login.",
        examples=[
            OpenApiExample(
                'Signup Request',
                value={
                    'email': 'newuser@example.com',
                    'password': 'securepassword123',
                    'password_confirm': 'securepassword123',
                    'first_name': 'John',
                    'last_name': 'Doe'
                },
                request_only=True
            )
        ]
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens for immediate login
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Account created successfully.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserWithProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    """
    Logout - blacklist the refresh token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout and invalidate tokens",
        description="Blacklist the refresh token to log out.",
        request={
            'type': 'object',
            'properties': {
                'refresh': {'type': 'string', 'description': 'Refresh token to blacklist'}
            }
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshAPIView(TokenRefreshView):
    """
    Refresh access token using refresh token.
    """

    @extend_schema(
        summary="Refresh access token",
        description="Use a valid refresh token to obtain a new access token."
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CurrentUserView(APIView):
    """
    Get current authenticated user's profile.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user",
        description="Returns the currently authenticated user's profile and settings."
    )
    def get(self, request):
        serializer = UserWithProfileSerializer(request.user)
        return Response(serializer.data)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update user profile.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer

    def get_object(self):
        return self.request.user.profile

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProfileUpdateSerializer
        return ProfileSerializer

    @extend_schema(
        summary="Get user profile",
        description="Returns the current user's profile settings."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update user profile",
        description="Update the current user's profile settings."
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update user profile",
        description="Update specific fields in the user's profile."
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class PasswordChangeView(APIView):
    """
    Change password for authenticated user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change password",
        description="Change the current user's password.",
        request=PasswordChangeSerializer
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # Change password
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        return Response({'message': 'Password changed successfully.'})


class DeleteAccountView(APIView):
    """
    Delete user account and all associated data.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete account",
        description="Permanently delete the user account and all associated data.",
        request={
            'type': 'object',
            'properties': {
                'password': {'type': 'string', 'description': 'Current password for confirmation'}
            }
        }
    )
    def post(self, request):
        password = request.data.get('password')

        if not password:
            return Response(
                {'error': 'Password is required to delete account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.check_password(password):
            return Response(
                {'error': 'Incorrect password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delete user (cascades to profile, entries, etc.)
        request.user.delete()

        return Response(
            {'message': 'Account deleted successfully.'},
            status=status.HTTP_200_OK
        )
