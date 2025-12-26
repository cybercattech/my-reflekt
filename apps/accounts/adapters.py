"""Custom allauth adapters for handling signup/login flow."""
from django.shortcuts import redirect
from django.urls import reverse
from django import forms
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm
from django.contrib import messages
from django.utils import timezone


class CustomSignupForm(SignupForm):
    """Custom signup form with terms and privacy acceptance."""
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

    def save(self, request):
        user = super().save(request)

        # Store terms acceptance in user profile
        profile = user.profile
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

    def get_email_confirmation_redirect_url(self, request):
        """
        Redirect user after email confirmation to the dashboard/overview.
        """
        messages.success(request, '✅ Email verified! Welcome to Reflekt.')
        return reverse('analytics:dashboard')
