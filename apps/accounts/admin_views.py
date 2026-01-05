"""
Custom admin dashboard views for subscription management.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Sum, Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import timedelta
from .models import Profile, Payment, SubscriptionHistory, Feedback
from django.contrib.auth.hashers import make_password
from allauth.account.models import EmailAddress
import secrets
import string


@staff_member_required
def subscription_dashboard(request):
    """Admin dashboard for subscription overview."""
    # Get date range
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # User counts by tier
    total_users = User.objects.count()
    premium_users = Profile.objects.filter(subscription_tier='premium').count()
    free_users = Profile.objects.filter(subscription_tier='free').count()

    # Recent changes (last 30 days)
    recent_upgrades = SubscriptionHistory.objects.filter(
        created_at__gte=thirty_days_ago,
        to_tier='premium'
    ).count()

    recent_downgrades = SubscriptionHistory.objects.filter(
        created_at__gte=thirty_days_ago,
        to_tier='free'
    ).count()

    # Payment stats (last 30 days)
    payments_last_30 = Payment.objects.filter(created_at__gte=thirty_days_ago)
    revenue_last_30 = payments_last_30.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0

    pending_payments = Payment.objects.filter(status='pending').count()
    failed_payments = Payment.objects.filter(status='failed').count()

    # All-time revenue
    total_revenue = Payment.objects.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Conversion rate
    conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0

    # Recent subscription changes
    recent_changes = SubscriptionHistory.objects.select_related('user', 'changed_by')[:20]

    # Recent payments
    recent_payments = Payment.objects.select_related('user')[:20]

    # Premium users list
    premium_user_list = User.objects.filter(
        profile__subscription_tier='premium'
    ).select_related('profile').order_by('-date_joined')[:10]

    context = {
        # Overview stats
        'total_users': total_users,
        'premium_users': premium_users,
        'free_users': free_users,
        'conversion_rate': round(conversion_rate, 1),

        # Recent activity
        'recent_upgrades': recent_upgrades,
        'recent_downgrades': recent_downgrades,

        # Revenue
        'revenue_last_30': revenue_last_30,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments,
        'failed_payments': failed_payments,

        # Lists
        'recent_changes': recent_changes,
        'recent_payments': recent_payments,
        'premium_user_list': premium_user_list,

        # Title
        'title': 'Subscription Dashboard',
        'active_page': 'subscriptions',
    }

    return render(request, 'admin/subscription_dashboard.html', context)


@staff_member_required
def admin_panel(request):
    """Main admin panel overview."""
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # Quick stats (no entry data for privacy)
    total_users = User.objects.count()
    premium_users = Profile.objects.filter(subscription_tier='premium').count()
    new_users_30 = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()

    # Recent users
    recent_users = User.objects.select_related('profile').order_by('-date_joined')[:5]

    context = {
        'total_users': total_users,
        'premium_users': premium_users,
        'free_users': total_users - premium_users,
        'new_users_30': new_users_30,
        'recent_users': recent_users,
        'title': 'Admin Panel',
        'active_page': 'overview',
    }

    return render(request, 'admin/panel.html', context)


@staff_member_required
def user_list(request):
    """List all users with filtering."""
    users = User.objects.select_related('profile').order_by('-date_joined')

    # Filtering
    tier_filter = request.GET.get('tier', '')
    search = request.GET.get('search', '')

    if tier_filter:
        users = users.filter(profile__subscription_tier=tier_filter)

    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(profile__username__icontains=search)
        )

    context = {
        'users': users,
        'tier_filter': tier_filter,
        'search': search,
        'title': 'User Management',
        'active_page': 'users',
    }

    return render(request, 'admin/user_list.html', context)


@staff_member_required
def user_detail(request, user_id):
    """View and edit user details."""
    user = get_object_or_404(User.objects.select_related('profile'), pk=user_id)

    # Check email verification status
    email_address = EmailAddress.objects.filter(user=user, email=user.email).first()
    email_verified = email_address.verified if email_address else False

    context = {
        'user_obj': user,
        'email_verified': email_verified,
        'title': f'User: {user.email}',
        'active_page': 'users',
    }

    return render(request, 'admin/user_detail.html', context)


@staff_member_required
@require_POST
def toggle_premium(request, user_id):
    """Toggle user's premium status."""
    user = get_object_or_404(User.objects.select_related('profile'), pk=user_id)
    profile = user.profile

    old_tier = profile.subscription_tier
    new_tier = 'free' if old_tier == 'premium' else 'premium'

    profile.subscription_tier = new_tier
    profile.save()

    # Log the change
    SubscriptionHistory.objects.create(
        user=user,
        from_tier=old_tier,
        to_tier=new_tier,
        change_type='manual_upgrade' if new_tier == 'premium' else 'manual_downgrade',
        changed_by=request.user,
        notes=f'Changed by admin: {request.user.email}'
    )

    messages.success(request, f'{user.email} is now {new_tier.upper()}')

    # Return JSON for AJAX or redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'new_tier': new_tier})

    return redirect('accounts:admin_user_list')


@staff_member_required
def delete_user(request, user_id):
    """Delete a user with typed confirmation."""
    user = get_object_or_404(User.objects.select_related('profile'), pk=user_id)

    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('accounts:admin_user_detail', user_id=user_id)

    if request.method == 'POST':
        confirmation = request.POST.get('confirmation', '').strip()

        if confirmation != 'Delete':
            messages.error(request, 'Please type "Delete" exactly to confirm.')
            return render(request, 'admin/user_delete.html', {
                'user_obj': user,
                'title': f'Delete User: {user.email}',
                'active_page': 'users',
            })

        email = user.email
        user.delete()
        messages.success(request, f'User "{email}" has been permanently deleted.')
        return redirect('accounts:admin_user_list')

    return render(request, 'admin/user_delete.html', {
        'user_obj': user,
        'title': f'Delete User: {user.email}',
        'active_page': 'users',
    })


@staff_member_required
def edit_user(request, user_id):
    """Edit user account details."""
    user = get_object_or_404(User.objects.select_related('profile'), pk=user_id)

    if request.method == 'POST':
        # Update user fields
        user.email = request.POST.get('email', user.email).strip()
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.is_superuser = request.POST.get('is_superuser') == 'on'
        user.is_active = request.POST.get('is_active') == 'on'

        # Update profile fields
        profile = user.profile
        profile.username = request.POST.get('username', '').strip() or None
        profile.subscription_tier = request.POST.get('subscription_tier', 'free')
        profile.city = request.POST.get('city', '').strip()
        profile.country_code = request.POST.get('country_code', '').strip().upper()
        profile.timezone = request.POST.get('timezone', '').strip()

        try:
            user.save()
            profile.save()
            messages.success(request, f'User "{user.email}" updated successfully.')
            return redirect('accounts:admin_user_detail', user_id=user_id)
        except Exception as e:
            messages.error(request, f'Error updating user: {str(e)}')

    return render(request, 'admin/user_edit.html', {
        'user_obj': user,
        'title': f'Edit User: {user.email}',
        'active_page': 'users',
    })


@staff_member_required
def create_user(request):
    """Create a new user account."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        username = request.POST.get('username', '').strip() or None
        subscription_tier = request.POST.get('subscription_tier', 'free')
        is_staff = request.POST.get('is_staff') == 'on'
        is_superuser = request.POST.get('is_superuser') == 'on'
        is_active = request.POST.get('is_active') == 'on'

        # Generate a random password
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

        if not email:
            messages.error(request, 'Email is required.')
            return render(request, 'admin/user_create.html', {
                'title': 'Create User',
                'active_page': 'users',
            })

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'A user with email "{email}" already exists.')
            return render(request, 'admin/user_create.html', {
                'title': 'Create User',
                'active_page': 'users',
            })

        try:
            # Create user with email as username (Django requires username)
            user = User.objects.create(
                username=email,
                email=email,
                password=make_password(password),
                is_staff=is_staff,
                is_superuser=is_superuser,
                is_active=is_active,
            )

            # Update profile (created via signal)
            profile = user.profile
            profile.username = username
            profile.subscription_tier = subscription_tier
            profile.save()

            messages.success(request, f'User "{email}" created successfully. Temporary password: {password}')
            return redirect('accounts:admin_user_detail', user_id=user.id)
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')

    return render(request, 'admin/user_create.html', {
        'title': 'Create User',
        'active_page': 'users',
    })


# =============================================================================
# Email Template Management
# =============================================================================

EMAIL_TEMPLATES = [
    # Subscription emails
    {
        'id': 'welcome',
        'name': 'Welcome Email',
        'description': 'Sent when a new user signs up',
        'template': 'accounts/emails/subscription/welcome.html',
        'subject': 'Welcome to Reflekt! Your journaling journey begins',
        'category': 'subscription',
    },
    {
        'id': 'trial_started',
        'name': 'Trial Started',
        'description': 'Sent when user starts their 14-day premium trial',
        'template': 'accounts/emails/subscription/trial_started.html',
        'subject': 'Your 14-day Premium trial has started!',
        'category': 'subscription',
    },
    {
        'id': 'trial_ending',
        'name': 'Trial Ending Reminder',
        'description': 'Sent 2 days before the trial ends',
        'template': 'accounts/emails/subscription/trial_ending.html',
        'subject': 'Your Reflekt trial ends in {days} days',
        'category': 'subscription',
    },
    {
        'id': 'payment_reminder',
        'name': 'Payment Reminder',
        'description': 'Sent 1 day before the card is charged',
        'template': 'accounts/emails/subscription/payment_reminder.html',
        'subject': 'Your Reflekt subscription renews tomorrow',
        'category': 'subscription',
    },
    {
        'id': 'payment_success',
        'name': 'Payment Success',
        'description': 'Sent after successful payment',
        'template': 'accounts/emails/subscription/payment_success.html',
        'subject': 'Thank you for your Reflekt subscription!',
        'category': 'subscription',
    },
    {
        'id': 'payment_failed',
        'name': 'Payment Failed',
        'description': 'Sent when payment fails and user is downgraded',
        'template': 'accounts/emails/subscription/payment_failed.html',
        'subject': 'Action required: Your Reflekt payment failed',
        'category': 'subscription',
    },
    # Family Plan emails
    {
        'id': 'family_invite_existing',
        'name': 'Family Invitation (Existing User)',
        'description': 'Sent when inviting an existing Reflekt user to your family plan',
        'template': 'accounts/emails/family/invitation_existing_user.html',
        'subject': '{admin_name} invited you to their Family Plan',
        'category': 'family',
    },
    {
        'id': 'family_invite_new',
        'name': 'Family Invitation (New User)',
        'description': 'Sent when inviting someone who doesn\'t have a Reflekt account yet',
        'template': 'accounts/emails/family/invitation_new_user.html',
        'subject': '{admin_name} invited you to join Reflekt Family Plan',
        'category': 'family',
    },
    {
        'id': 'family_member_joined',
        'name': 'Family Member Joined',
        'description': 'Sent to admin when someone accepts their family plan invitation',
        'template': 'accounts/emails/family/member_joined.html',
        'subject': '{member_name} joined your Family Plan!',
        'category': 'family',
    },
    # Friend emails
    {
        'id': 'friend_request',
        'name': 'Friend Request',
        'description': 'Sent when someone sends you a friend request',
        'template': 'accounts/emails/friend_request.html',
        'subject': '{sender_name} wants to be your friend on Reflekt',
        'category': 'friends',
    },
    {
        'id': 'friend_request_accepted',
        'name': 'Friend Request Accepted',
        'description': 'Sent when someone accepts your friend request',
        'template': 'accounts/emails/friend_request_accepted.html',
        'subject': '{friend_name} accepted your friend request!',
        'category': 'friends',
    },
    {
        'id': 'invitation',
        'name': 'Invitation to Join',
        'description': 'Sent when inviting someone new to Reflekt',
        'template': 'accounts/emails/invitation.html',
        'subject': '{sender_name} invited you to join Reflekt',
        'category': 'friends',
    },
    # POV emails
    {
        'id': 'pov_shared',
        'name': 'POV Shared',
        'description': 'Sent when a friend shares a POV with you',
        'template': 'journal/emails/pov_shared.html',
        'subject': '{sender_name} shared a thought with you',
        'category': 'pov',
    },
]


def _get_sample_context(template_id):
    """Get sample context data for previewing email templates."""
    from datetime import datetime, timedelta

    base_context = {
        'user_name': 'John',
        'site_url': 'https://myreflekt.net',
    }

    if template_id == 'welcome':
        return base_context

    elif template_id == 'trial_started':
        return {
            **base_context,
            'trial_end_date': datetime.now() + timedelta(days=14),
        }

    elif template_id == 'trial_ending':
        return {
            **base_context,
            'days_remaining': 2,
            'trial_end_date': datetime.now() + timedelta(days=2),
        }

    elif template_id == 'payment_reminder':
        return {
            **base_context,
            'charge_date': datetime.now() + timedelta(days=1),
            'amount': '10.00',
            'plan_name': 'Individual Monthly',
        }

    elif template_id == 'payment_success':
        return {
            **base_context,
            'amount': '10.00',
            'plan_name': 'Individual Monthly',
            'next_billing_date': datetime.now() + timedelta(days=30),
        }

    elif template_id == 'payment_failed':
        return base_context

    # Family Plan emails
    elif template_id == 'family_invite_existing':
        return {
            **base_context,
            'admin_name': 'Sarah',
            'admin_email': 'sarah@example.com',
            'member_name': 'John',
            'member_email': 'john@example.com',
            'accept_url': 'https://myreflekt.net/accounts/family/accept/123/',
        }

    elif template_id == 'family_invite_new':
        return {
            **base_context,
            'admin_name': 'Sarah',
            'admin_email': 'sarah@example.com',
            'invited_email': 'newuser@example.com',
            'signup_url': 'https://myreflekt.net/accounts/signup/',
        }

    elif template_id == 'family_member_joined':
        return {
            **base_context,
            'admin_name': 'Sarah',
            'member_name': 'John',
            'member_email': 'john@example.com',
            'member_count': 2,
        }

    # Friend emails
    elif template_id == 'friend_request':
        return {
            **base_context,
            'sender_name': 'Sarah',
            'sender_email': 'sarah@example.com',
            'accept_url': 'https://myreflekt.net/accounts/friends/accept/123/',
        }

    elif template_id == 'friend_request_accepted':
        return {
            **base_context,
            'friend_name': 'Sarah',
        }

    elif template_id == 'invitation':
        return {
            **base_context,
            'sender_name': 'Sarah',
            'sender_email': 'sarah@example.com',
            'message': 'Hey! Join me on Reflekt, it\'s a great journaling app!',
            'signup_url': 'https://myreflekt.net/accounts/signup/',
        }

    # POV emails
    elif template_id == 'pov_shared':
        return {
            **base_context,
            'sender_name': 'Sarah',
            'pov_preview': 'I just had the most amazing day at the beach...',
            'view_url': 'https://myreflekt.net/journal/povs/',
        }

    return base_context


@staff_member_required
def email_templates_list(request):
    """List all email templates for preview."""
    return render(request, 'admin/email_templates.html', {
        'templates': EMAIL_TEMPLATES,
        'title': 'Email Templates',
        'active_page': 'emails',
    })


@staff_member_required
def email_template_preview(request, template_id):
    """Preview a specific email template."""
    from django.template.loader import render_to_string
    from django.http import HttpResponse

    # Find the template
    template_info = next((t for t in EMAIL_TEMPLATES if t['id'] == template_id), None)
    if not template_info:
        messages.error(request, 'Template not found.')
        return redirect('accounts:admin_email_templates')

    # Get sample context
    context = _get_sample_context(template_id)

    # Render the template
    try:
        html_content = render_to_string(template_info['template'], context)
        return HttpResponse(html_content)
    except Exception as e:
        messages.error(request, f'Error rendering template: {str(e)}')
        return redirect('accounts:admin_email_templates')


@staff_member_required
def send_test_email(request, template_id):
    """Send a test email to the current user."""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings

    # Find the template
    template_info = next((t for t in EMAIL_TEMPLATES if t['id'] == template_id), None)
    if not template_info:
        messages.error(request, 'Template not found.')
        return redirect('accounts:admin_email_templates')

    # Get sample context
    context = _get_sample_context(template_id)
    context['user_name'] = request.user.profile.display_name or request.user.email.split('@')[0]

    # Render templates
    try:
        html_content = render_to_string(template_info['template'], context)
        txt_template = template_info['template'].replace('.html', '.txt')
        txt_content = render_to_string(txt_template, context)

        # Send email
        send_mail(
            subject=f"[TEST] {template_info['subject']}",
            message=txt_content,
            html_message=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )

        messages.success(request, f'Test email sent to {request.user.email}')
    except Exception as e:
        messages.error(request, f'Error sending email: {str(e)}')

    return redirect('accounts:admin_email_templates')


# =============================================================================
# Feedback Management
# =============================================================================

@staff_member_required
def feedback_list(request):
    """List all user feedback with filtering."""
    feedback_items = Feedback.objects.select_related('user', 'user__profile').order_by('-created_at')

    # Filtering
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    if status_filter:
        feedback_items = feedback_items.filter(status=status_filter)
    if type_filter:
        feedback_items = feedback_items.filter(feedback_type=type_filter)

    # Stats
    total_count = Feedback.objects.count()
    new_count = Feedback.objects.filter(status='new').count()
    bug_count = Feedback.objects.filter(feedback_type='bug').count()
    idea_count = Feedback.objects.filter(feedback_type='idea').count()

    context = {
        'feedback_items': feedback_items,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'total_count': total_count,
        'new_count': new_count,
        'bug_count': bug_count,
        'idea_count': idea_count,
        'title': 'User Feedback',
        'active_page': 'feedback',
    }

    return render(request, 'admin/feedback_list.html', context)


@staff_member_required
def feedback_detail(request, feedback_id):
    """View and update feedback details."""
    feedback = get_object_or_404(Feedback.objects.select_related('user', 'user__profile'), pk=feedback_id)

    if request.method == 'POST':
        new_status = request.POST.get('status', feedback.status)
        admin_notes = request.POST.get('admin_notes', '')

        feedback.status = new_status
        feedback.admin_notes = admin_notes
        feedback.save()

        messages.success(request, 'Feedback updated successfully.')
        return redirect('accounts:admin_feedback_detail', feedback_id=feedback_id)

    context = {
        'feedback': feedback,
        'title': f'Feedback: {feedback.subject[:30]}...',
        'active_page': 'feedback',
    }

    return render(request, 'admin/feedback_detail.html', context)


@staff_member_required
@require_POST
def feedback_update_status(request, feedback_id):
    """Quick status update for feedback."""
    feedback = get_object_or_404(Feedback, pk=feedback_id)
    new_status = request.POST.get('status', feedback.status)

    feedback.status = new_status
    feedback.save()

    messages.success(request, f'Status updated to {feedback.get_status_display()}')

    # Return to list or detail based on referrer
    if 'detail' in request.META.get('HTTP_REFERER', ''):
        return redirect('accounts:admin_feedback_detail', feedback_id=feedback_id)
    return redirect('accounts:admin_feedback_list')


# =============================================================================
# User Email Verification & Password Reset
# =============================================================================

@staff_member_required
@require_POST
def verify_user_email(request, user_id):
    """Manually verify a user's email address."""
    user = get_object_or_404(User, pk=user_id)

    # Get or create EmailAddress for this user
    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={'verified': False, 'primary': True}
    )

    if email_address.verified:
        messages.info(request, f'Email for {user.email} is already verified.')
    else:
        email_address.verified = True
        email_address.save()
        messages.success(request, f'Email for {user.email} has been verified.')

    return redirect('accounts:admin_user_detail', user_id=user_id)


@staff_member_required
@require_POST
def unverify_user_email(request, user_id):
    """Unverify a user's email address (useful for testing)."""
    user = get_object_or_404(User, pk=user_id)

    email_address = EmailAddress.objects.filter(user=user, email=user.email).first()

    if email_address:
        email_address.verified = False
        email_address.save()
        messages.success(request, f'Email for {user.email} has been unverified.')
    else:
        messages.warning(request, f'No email address record found for {user.email}.')

    return redirect('accounts:admin_user_detail', user_id=user_id)


@staff_member_required
@require_POST
def reset_user_password(request, user_id):
    """Reset user's password - either generate new or send reset email."""
    user = get_object_or_404(User, pk=user_id)
    action = request.POST.get('action', 'generate')

    if action == 'generate':
        # Generate a new random password
        new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        user.set_password(new_password)
        user.save()

        messages.success(
            request,
            f'Password reset for {user.email}. New temporary password: {new_password}'
        )

    elif action == 'send_email':
        # Send password reset email using allauth
        from allauth.account.forms import ResetPasswordForm
        from django.contrib.sites.shortcuts import get_current_site

        try:
            form = ResetPasswordForm(data={'email': user.email})
            if form.is_valid():
                form.save(request)
                messages.success(
                    request,
                    f'Password reset email sent to {user.email}.'
                )
            else:
                messages.error(request, 'Could not send password reset email.')
        except Exception as e:
            messages.error(request, f'Error sending reset email: {str(e)}')

    return redirect('accounts:admin_user_detail', user_id=user_id)
