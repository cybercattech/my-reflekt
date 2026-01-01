"""Custom allauth adapters for handling signup/login flow."""
from django.shortcuts import redirect
from django.urls import reverse
from django import forms
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm
from django.contrib import messages
from django.utils import timezone


class CustomSignupForm(SignupForm):
    """Custom signup form with username, terms and privacy acceptance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add username field after email
        self.fields['username'] = forms.CharField(
            required=True,
            min_length=3,
            max_length=30,
            label='Username',
            widget=forms.TextInput(attrs={
                'placeholder': 'your_username',
                'pattern': '[a-zA-Z0-9_]+',
                'class': 'form-control',
            }),
            help_text='Your unique @username for friends to find you. Letters, numbers, and underscores only.',
            error_messages={'required': 'Username is required.'}
        )
        # Reorder fields to put username after email
        field_order = ['email', 'username', 'password1', 'password2', 'terms_accepted', 'privacy_accepted']
        self.order_fields(field_order)

    terms_accepted = forms.BooleanField(
        required=True,
        label='',
        error_messages={'required': 'You must accept the Terms of Service to create an account.'}
    )
    privacy_accepted = forms.BooleanField(
        required=True,
        label='',
        error_messages={'required': 'You must accept the Privacy Policy to create an account.'}
    )

    def clean_username(self):
        """Validate username is unique and properly formatted."""
        from .models import Profile
        import re

        username = self.cleaned_data.get('username', '').strip().lower()

        if not username:
            raise forms.ValidationError('Username is required.')

        if len(username) < 3:
            raise forms.ValidationError('Username must be at least 3 characters.')

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise forms.ValidationError('Username can only contain letters, numbers, and underscores.')

        if Profile.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')

        return username

    def save(self, request):
        user = super().save(request)

        # Store terms acceptance and username in user profile
        profile = user.profile
        profile.username = self.cleaned_data.get('username').lower()
        profile.terms_accepted = self.cleaned_data.get('terms_accepted')
        profile.privacy_accepted = self.cleaned_data.get('privacy_accepted')
        profile.terms_accepted_at = timezone.now()
        profile.privacy_accepted_at = timezone.now()
        profile.save()

        # Check for pending family plan invitation
        from .models import Invitation, FamilyMember, Friendship
        from django.db import models as django_models

        # Check if user was invited to a family plan
        pending_invitation = Invitation.objects.filter(
            email=user.email.lower(),
            status='pending'
        ).first()

        if pending_invitation:
            # Create family membership
            family_member = FamilyMember.objects.create(
                admin=pending_invitation.sender,
                member=user,
                role='member',
                status='active'
            )

            # Upgrade to premium
            profile.subscription_tier = 'premium'
            profile.save()

            # Make them friends automatically
            admin = pending_invitation.sender
            if not Friendship.objects.filter(
                django_models.Q(user1=user, user2=admin) |
                django_models.Q(user1=admin, user2=user)
            ).exists():
                Friendship.objects.create(
                    user1=user,
                    user2=admin
                )

            # Mark invitation as accepted
            pending_invitation.status = 'accepted'
            pending_invitation.save()

        return user


class AccountAdapter(DefaultAccountAdapter):
    """Custom account adapter to handle post-signup plan selection."""

    def get_signup_redirect_url(self, request):
        """
        Redirect user after signup based on selected plan in session.
        """
        selected_plan = request.session.get('selected_plan')

        # Clear the selected plan from session
        if 'selected_plan' in request.session:
            del request.session['selected_plan']

        # If no plan selected or free plan, go to dashboard
        if not selected_plan or selected_plan == 'free':
            messages.success(request, '🎉 Welcome to Reflekt! Start writing your first entry.')
            return reverse('analytics:dashboard')

        # For paid plans, redirect to checkout
        # Store the plan for the create_checkout view
        request.session['pending_plan'] = selected_plan
        messages.info(request, 'Complete your payment to unlock premium features!')
        return reverse('accounts:process_plan_selection')

    def get_email_verification_redirect_url(self, email_address):
        """
        Redirect user after email verification to the dashboard.
        Note: New allauth API uses email_address instead of request.
        """
        return reverse('analytics:dashboard')

    def get_login_redirect_url(self, request):
        """
        Redirect user after login to the dashboard.
        """
        return reverse('analytics:dashboard')

