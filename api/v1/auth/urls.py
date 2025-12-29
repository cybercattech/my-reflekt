"""
Authentication URL patterns for the Reflekt API.
"""
from django.urls import path

from .views import (
    LoginView,
    SignupView,
    LogoutView,
    TokenRefreshAPIView,
    CurrentUserView,
    ProfileView,
    PasswordChangeView,
    DeleteAccountView,
)

urlpatterns = [
    # Authentication
    path('login/', LoginView.as_view(), name='login'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshAPIView.as_view(), name='token_refresh'),

    # User profile
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('profile/', ProfileView.as_view(), name='profile'),

    # Password management
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),

    # Account management
    path('account/delete/', DeleteAccountView.as_view(), name='delete_account'),
]
