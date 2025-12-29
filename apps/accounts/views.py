from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone as django_timezone
from django.views.generic import TemplateView

from .models import Profile, Friendship, FriendRequest, Invitation
from .services.friends import (
    send_friend_request,
    accept_friend_request,
    deny_friend_request,
    cancel_friend_request,
    unfriend,
    accept_invitation,
    deny_invitation,
    get_pending_friend_requests,
    get_pending_invitations,
    search_users_by_username,
    FriendshipError,
)


@login_required
def profile_view(request):
    """User profile and settings page."""
    profile = request.user.profile
    friends = Friendship.get_friends(request.user)
    pending = get_pending_friend_requests(request.user)
    invitations = get_pending_invitations(request.user)

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'friends': friends,
        'pending_received': pending['received'],
        'pending_sent': pending['sent'],
        'invitations_sent': invitations['sent'],
        'invitations_received': invitations['received'],
        'active_page': None,  # Profile is not in the sidebar
    })


@login_required
def profile_update(request):
    """Update user profile settings."""
    if request.method == 'POST':
        profile = request.user.profile

        # Check if this is the insights form
        is_insights_form = request.POST.get('insights_form') == '1'

        if is_insights_form:
            # Handle insights form fields
            profile.city = request.POST.get('city', '').strip()
            profile.country_code = request.POST.get('country_code', 'US')

            # Handle birthday
            birthday_str = request.POST.get('birthday', '')
            if birthday_str:
                from datetime import datetime
                try:
                    profile.birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, 'Invalid birthday format.')
                    return redirect('accounts:profile')
            else:
                profile.birthday = None

            # Handle horoscope toggle
            profile.horoscope_enabled = request.POST.get('horoscope_enabled') == '1'

            # Handle devotion toggle
            profile.devotion_enabled = request.POST.get('devotion_enabled') == '1'

            profile.save()
            messages.success(request, 'Insights settings updated successfully.')
            return redirect('accounts:profile')

        # Handle main preferences form
        profile.timezone = request.POST.get('timezone', profile.timezone)
        profile.editor_preference = request.POST.get('editor_preference', profile.editor_preference)

        # Handle username update
        new_username = request.POST.get('username', '').strip().lower()
        if new_username:
            if new_username != profile.username:
                # Validate username
                if len(new_username) < 3:
                    messages.error(request, 'Username must be at least 3 characters.')
                    return redirect('accounts:profile')
                if not new_username.replace('_', '').isalnum():
                    messages.error(request, 'Username can only contain letters, numbers, and underscores.')
                    return redirect('accounts:profile')
                if Profile.objects.filter(username=new_username).exclude(user=request.user).exists():
                    messages.error(request, 'This username is already taken.')
                    return redirect('accounts:profile')
                profile.username = new_username
        elif profile.username and not new_username:
            # Allow clearing username
            profile.username = None

        profile.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')
    return redirect('accounts:profile')


# =============================================================================
# Friends Management Views
# =============================================================================

@login_required
@require_POST
def send_friend_request_view(request):
    """Send a friend request or invitation."""
    email = request.POST.get('email', '').strip()
    message = request.POST.get('message', '').strip()

    if not email:
        messages.error(request, 'Please enter an email address.')
        return redirect('accounts:profile')

    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, 'Please enter a valid email address.')
        return redirect('accounts:profile')

    try:
        result_type, result = send_friend_request(request.user, email, message)
        if result_type == 'friend_request':
            messages.success(request, f'Friend request sent to {email}!')
        elif result_type == 'friendship':
            # Auto-accepted because they had already sent a request
            messages.success(request, f'You are now friends with {email}!')
        else:
            messages.success(request, f'Invitation sent to {email}! They will be notified by email.')
    except FriendshipError as e:
        messages.error(request, str(e))

    return redirect('accounts:profile')


@login_required
@require_POST
def accept_friend_request_view(request, request_id):
    """Accept a friend request."""
    try:
        accept_friend_request(request.user, request_id)
        messages.success(request, 'Friend request accepted!')
    except FriendshipError as e:
        messages.error(request, str(e))

    if request.headers.get('HX-Request'):
        # HTMX request - return updated pending list
        pending = get_pending_friend_requests(request.user)
        return render(request, 'accounts/friends/partials/_pending_requests.html', {
            'pending_received': pending['received'],
        })
    return redirect('accounts:profile')


@login_required
@require_POST
def deny_friend_request_view(request, request_id):
    """Deny a friend request."""
    try:
        deny_friend_request(request.user, request_id)
        messages.info(request, 'Friend request declined.')
    except FriendshipError as e:
        messages.error(request, str(e))

    if request.headers.get('HX-Request'):
        pending = get_pending_friend_requests(request.user)
        return render(request, 'accounts/friends/partials/_pending_requests.html', {
            'pending_received': pending['received'],
        })
    return redirect('accounts:profile')


@login_required
@require_POST
def cancel_friend_request_view(request, request_id):
    """Cancel a sent friend request."""
    try:
        cancel_friend_request(request.user, request_id)
        messages.info(request, 'Friend request cancelled.')
    except FriendshipError as e:
        messages.error(request, str(e))

    return redirect('accounts:profile')


@login_required
@require_POST
def unfriend_view(request, friend_id):
    """Remove a friend."""
    try:
        unfriend(request.user, friend_id)
        messages.info(request, 'Friend removed.')
    except FriendshipError as e:
        messages.error(request, str(e))

    return redirect('accounts:profile')


@login_required
@require_POST
def accept_invitation_view(request, invitation_id):
    """Accept an invitation (for new users who received invites before signing up)."""
    try:
        accept_invitation(request.user, invitation_id)
        messages.success(request, 'Invitation accepted! You are now friends.')
    except FriendshipError as e:
        messages.error(request, str(e))

    return redirect('accounts:profile')


@login_required
@require_POST
def deny_invitation_view(request, invitation_id):
    """Deny an invitation."""
    try:
        deny_invitation(request.user, invitation_id)
        messages.info(request, 'Invitation declined.')
    except FriendshipError as e:
        messages.error(request, str(e))

    return redirect('accounts:profile')


@login_required
@require_POST
def cancel_invitation_view(request, invitation_id):
    """Cancel a sent invitation."""
    try:
        invitation = Invitation.objects.get(
            id=invitation_id,
            sender=request.user,
            status='pending'
        )
        invitation.status = 'cancelled'
        invitation.save()
        messages.info(request, 'Invitation cancelled.')
    except Invitation.DoesNotExist:
        messages.error(request, 'Invitation not found.')

    return redirect('accounts:profile')


@login_required
@require_GET
def search_users_view(request):
    """AJAX endpoint for username search autocomplete."""
    query = request.GET.get('q', '')
    profiles = search_users_by_username(query, exclude_user=request.user)

    results = [
        {
            'id': p.user.id,
            'username': p.username,
            'display_name': p.display_name,
            'email': p.user.email,
        }
        for p in profiles
    ]

    return JsonResponse({'results': results})


@login_required
def friends_list_api(request):
    """API endpoint to get current user's friends list for @ mention autocomplete."""
    from .models import Friendship

    friends = Friendship.get_friends(request.user)

    results = [
        {
            'id': f.id,
            'username': f.profile.username,
            'display_name': f.profile.display_name,
        }
        for f in friends if f.profile.username  # Only include friends with usernames
    ]

    # Sort alphabetically by username
    results.sort(key=lambda x: x['username'].lower())

    return JsonResponse({'friends': results})


# =============================================================================
# Subscription / Pricing Views
# =============================================================================

def pricing_view(request):
    """Public pricing page."""
    return render(request, 'accounts/pricing.html')


def select_plan(request):
    """Store selected plan in session and redirect to signup."""
    plan = request.GET.get('plan', 'free')

    # Valid plan choices
    valid_plans = ['free', 'individual_monthly', 'individual_yearly', 'family_monthly', 'family_yearly']

    if plan not in valid_plans:
        plan = 'free'

    # Store plan in session
    request.session['selected_plan'] = plan

    # Add a message about the selected plan
    if plan == 'free':
        messages.info(request, 'Create your free account to start journaling!')
    elif 'individual' in plan:
        period = 'monthly' if 'monthly' in plan else 'yearly'
        messages.info(request, f'Create your account to continue with Individual ({period}) plan.')
    else:  # family plan
        period = 'monthly' if 'monthly' in plan else 'yearly'
        messages.info(request, f'Create your account to continue with Family ({period}) plan.')

    # Redirect to signup
    return redirect('account_signup')


@login_required
def process_plan_selection(request):
    """Process plan selection after signup and redirect to checkout or dashboard."""
    pending_plan = request.session.get('pending_plan')

    # Clear pending plan from session
    if 'pending_plan' in request.session:
        del request.session['pending_plan']

    # If no pending plan or free plan, go to dashboard
    if not pending_plan or pending_plan == 'free':
        return redirect('analytics:dashboard')

    # For paid plans, create checkout session
    import stripe
    from django.conf import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = settings.STRIPE_PRICE_IDS.get(pending_plan)

    if not price_id:
        messages.error(request, 'Selected plan is not available. Please contact support.')
        return redirect('accounts:pricing')

    try:
        # Create or get Stripe customer
        profile = request.user.profile
        if profile.stripe_customer_id:
            customer_id = profile.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={
                    'user_id': request.user.id,
                }
            )
            customer_id = customer.id
            profile.stripe_customer_id = customer_id
            profile.save()

        # Create checkout session with 14-day trial
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            subscription_data={
                'trial_period_days': 14,  # 14-day free trial
            },
            success_url=request.build_absolute_uri('/accounts/checkout/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/accounts/checkout/cancel/'),
            metadata={
                'user_id': request.user.id,
                'plan': pending_plan,
            },
        )

        return redirect(checkout_session.url)

    except stripe.error.StripeError as e:
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('accounts:pricing')
    except Exception as e:
        messages.error(request, 'An error occurred. Please try again.')
        return redirect('accounts:pricing')


@login_required
def upgrade_view(request):
    """Upgrade to premium page - redirects to pricing."""
    return redirect('accounts:pricing')


@login_required
@require_POST
def create_checkout(request):
    """Create Stripe checkout session for subscription."""
    import stripe
    from django.conf import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY
    plan = request.POST.get('plan', 'individual_monthly')

    # Validate plan
    if plan not in settings.STRIPE_PRICE_IDS:
        messages.error(request, 'Invalid plan selected.')
        return redirect('accounts:pricing')

    price_id = settings.STRIPE_PRICE_IDS[plan]
    if not price_id:
        messages.error(request, 'This plan is not configured yet. Please contact support.')
        return redirect('accounts:pricing')

    try:
        # Create or get Stripe customer
        profile = request.user.profile
        if profile.stripe_customer_id:
            customer_id = profile.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={
                    'user_id': request.user.id,
                }
            )
            customer_id = customer.id
            profile.stripe_customer_id = customer_id
            profile.save()

        # Create checkout session with 14-day trial
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            subscription_data={
                'trial_period_days': 14,  # 14-day free trial
            },
            success_url=request.build_absolute_uri('/accounts/checkout/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/accounts/checkout/cancel/'),
            metadata={
                'user_id': request.user.id,
                'plan': plan,
            },
        )

        return redirect(checkout_session.url)

    except stripe.error.StripeError as e:
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('accounts:pricing')
    except Exception as e:
        messages.error(request, 'An error occurred. Please try again.')
        return redirect('accounts:pricing')


@login_required
def checkout_success(request):
    """Handle successful checkout."""
    session_id = request.GET.get('session_id')

    if session_id:
        import stripe
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            # Retrieve the session
            session = stripe.checkout.Session.retrieve(session_id)

            # Update user profile
            profile = request.user.profile
            profile.stripe_subscription_id = session.subscription
            profile.subscription_status = 'active'
            profile.subscription_plan = session.metadata.get('plan')
            profile.subscription_tier = 'premium'
            profile.subscription_start_date = django_timezone.now()
            profile.save()

            # Log subscription change
            from .models import SubscriptionHistory
            SubscriptionHistory.objects.create(
                user=request.user,
                from_tier='free',
                to_tier='premium',
                change_type='upgrade',
                notes=f'Upgraded via Stripe to {session.metadata.get("plan")}'
            )

            messages.success(request, '🎉 Welcome to Premium! All features are now unlocked.')
            return redirect('analytics:dashboard')

        except Exception as e:
            messages.error(request, 'There was an issue confirming your subscription. Please contact support.')
            return redirect('accounts:profile')

    return redirect('accounts:pricing')


@login_required
def checkout_cancel(request):
    """Handle cancelled checkout."""
    messages.info(request, 'Checkout was cancelled. You can try again anytime!')
    return redirect('accounts:pricing')


@login_required
def manage_subscription(request):
    """Manage subscription - view details and cancel."""
    profile = request.user.profile

    subscription_details = None
    if profile.stripe_subscription_id:
        import stripe
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            subscription_details = stripe.Subscription.retrieve(profile.stripe_subscription_id)
        except stripe.error.StripeError:
            pass  # Subscription not found or error

    return render(request, 'accounts/manage_subscription.html', {
        'profile': profile,
        'subscription': subscription_details,
        'active_page': None,
    })


@login_required
@require_POST
def cancel_subscription(request):
    """Cancel user's subscription."""
    profile = request.user.profile

    if not profile.stripe_subscription_id:
        messages.error(request, 'No active subscription found.')
        return redirect('accounts:manage_subscription')

    import stripe
    from django.conf import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # Cancel at period end (user keeps access until end of billing period)
        subscription = stripe.Subscription.modify(
            profile.stripe_subscription_id,
            cancel_at_period_end=True
        )

        messages.success(request, 'Your subscription has been cancelled. You will retain access until the end of your current billing period.')
        return redirect('accounts:manage_subscription')

    except stripe.error.StripeError as e:
        messages.error(request, f'Error cancelling subscription: {str(e)}')
        return redirect('accounts:manage_subscription')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    import stripe
    from django.conf import settings
    from django.http import HttpResponse

    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event
    if event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        _handle_subscription_updated(subscription)

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        _handle_subscription_deleted(subscription)

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        _handle_payment_succeeded(invoice)

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        _handle_payment_failed(invoice)

    return HttpResponse(status=200)


def _handle_subscription_updated(subscription):
    """Handle subscription update webhook."""
    from .models import Profile, SubscriptionHistory
    from django.contrib.auth.models import User

    customer_id = subscription['customer']
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)
        old_status = profile.subscription_status

        profile.subscription_status = subscription['status']
        profile.stripe_subscription_id = subscription['id']

        # Update tier based on status
        if subscription['status'] == 'active':
            profile.subscription_tier = 'premium'
        elif subscription['status'] in ['canceled', 'incomplete', 'past_due']:
            profile.subscription_tier = 'free'

        profile.save()

        # Log if status changed
        if old_status != subscription['status']:
            SubscriptionHistory.objects.create(
                user=profile.user,
                from_tier='premium' if old_status == 'active' else 'free',
                to_tier=profile.subscription_tier,
                change_type='upgrade' if profile.subscription_tier == 'premium' else 'downgrade',
                notes=f'Stripe webhook: subscription status changed to {subscription["status"]}'
            )

    except Profile.DoesNotExist:
        pass  # Customer not found


def _handle_subscription_deleted(subscription):
    """Handle subscription deletion webhook."""
    from .models import Profile, SubscriptionHistory

    customer_id = subscription['customer']
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)

        # Downgrade to free
        old_tier = profile.subscription_tier
        profile.subscription_tier = 'free'
        profile.subscription_status = 'canceled'
        profile.subscription_end_date = django_timezone.now()
        profile.save()

        # Log the change
        SubscriptionHistory.objects.create(
            user=profile.user,
            from_tier=old_tier,
            to_tier='free',
            change_type='downgrade',
            notes='Stripe webhook: subscription deleted'
        )

    except Profile.DoesNotExist:
        pass


def _handle_payment_succeeded(invoice):
    """Handle successful payment webhook."""
    from .models import Profile, Payment
    from datetime import datetime

    customer_id = invoice['customer']
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)

        # Create payment record
        Payment.objects.create(
            user=profile.user,
            amount=invoice['amount_paid'] / 100,  # Convert cents to dollars
            status='completed',
            payment_method='stripe',
            stripe_payment_intent_id=invoice.get('payment_intent', ''),
            stripe_customer_id=customer_id,
            period_start=datetime.fromtimestamp(invoice['period_start']),
            period_end=datetime.fromtimestamp(invoice['period_end']),
            completed_at=django_timezone.now(),
        )

    except Profile.DoesNotExist:
        pass


def _handle_payment_failed(invoice):
    """Handle failed payment webhook."""
    from .models import Profile, Payment, SubscriptionHistory
    from datetime import datetime

    customer_id = invoice['customer']
    try:
        profile = Profile.objects.get(stripe_customer_id=customer_id)

        # Create failed payment record
        Payment.objects.create(
            user=profile.user,
            amount=invoice['amount_due'] / 100,
            status='failed',
            payment_method='stripe',
            stripe_payment_intent_id=invoice.get('payment_intent', ''),
            stripe_customer_id=customer_id,
            period_start=datetime.fromtimestamp(invoice['period_start']),
            period_end=datetime.fromtimestamp(invoice['period_end']),
        )

        # Update subscription status
        if profile.subscription_status != 'past_due':
            old_tier = profile.subscription_tier
            profile.subscription_status = 'past_due'
            profile.save()

            # Log the change
            SubscriptionHistory.objects.create(
                user=profile.user,
                from_tier=old_tier,
                to_tier=profile.subscription_tier,
                change_type='payment_failed',
                notes='Stripe webhook: payment failed'
            )

    except Profile.DoesNotExist:
        pass


# =============================================================================
# Family Plan Management
# =============================================================================

@login_required
def family_management(request):
    """Family plan management page for admins."""
    from .models import FamilyMember

    profile = request.user.profile

    # Check if user has a family plan
    has_family_plan = profile.subscription_plan in ['family_monthly', 'family_yearly']

    if not has_family_plan:
        messages.warning(request, 'You need a Family plan to manage family members.')
        return redirect('accounts:upgrade')

    # Get family members
    family_members = FamilyMember.get_active_members(request.user)
    member_count = family_members.count()
    max_members = 5  # Maximum family members (configurable)

    return render(request, 'accounts/family_management.html', {
        'family_members': family_members,
        'member_count': member_count,
        'max_members': max_members,
        'slots_remaining': max_members - member_count,
    })


@login_required
@require_POST
def remove_family_member(request, member_id):
    """Remove a member from the family plan."""
    from .models import FamilyMember
    from django.contrib.auth.models import User

    profile = request.user.profile

    # Check if user has a family plan
    if profile.subscription_plan not in ['family_monthly', 'family_yearly']:
        return JsonResponse({'success': False, 'error': 'You do not have a family plan'}, status=403)

    try:
        # Get the family member
        family_member = FamilyMember.objects.get(
            id=member_id,
            admin=request.user,
            status='active'
        )

        # Don't allow removing yourself
        if family_member.member == request.user:
            return JsonResponse({'success': False, 'error': 'Cannot remove yourself from the family plan'}, status=400)

        # Remove the member (soft delete)
        family_member.status = 'removed'
        family_member.removed_at = django_timezone.now()
        family_member.removed_by = request.user
        family_member.save()

        # Downgrade the member to free tier
        member_profile = family_member.member.profile
        member_profile.subscription_tier = 'free'
        member_profile.save()

        messages.success(request, f'{family_member.member.email} has been removed from your family plan.')

        return JsonResponse({
            'success': True,
            'message': f'{family_member.member.email} removed successfully',
            'member_email': family_member.member.email
        })

    except FamilyMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Family member not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def add_family_member(request):
    """Send invitation to join family plan by email."""
    from .models import FamilyMember, Invitation, FriendRequest
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.urls import reverse
    from django.conf import settings

    profile = request.user.profile

    # Check if user has a family plan
    if profile.subscription_plan not in ['family_monthly', 'family_yearly']:
        return JsonResponse({'success': False, 'error': 'You do not have a family plan'}, status=403)

    # Check family member limit (count active + pending)
    current_count = FamilyMember.objects.filter(
        admin=request.user,
        status__in=['active', 'pending']
    ).exclude(member=request.user).count()
    max_members = 5

    if current_count >= max_members:
        return JsonResponse({'success': False, 'error': f'Family plan limit reached ({max_members} members max)'}, status=400)

    # Get email from request
    email = request.POST.get('email', '').strip().lower()

    if not email:
        return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)

    # Validate email
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'success': False, 'error': 'Invalid email address'}, status=400)

    # Check if it's the admin's own email
    if email == request.user.email:
        return JsonResponse({'success': False, 'error': 'Cannot add yourself as a family member'}, status=400)

    # Try to find existing user
    try:
        member_user = User.objects.get(email=email)
        user_exists = True
    except User.DoesNotExist:
        user_exists = False
        member_user = None

    if user_exists:
        # Check if already in this family (active or pending)
        if FamilyMember.objects.filter(
            admin=request.user,
            member=member_user,
            status__in=['active', 'pending']
        ).exists():
            return JsonResponse({'success': False, 'error': 'This user already has an invitation or is in your family plan'}, status=400)

        # Check if member is in another family
        existing_membership = FamilyMember.objects.filter(member=member_user, status='active').first()
        if existing_membership:
            return JsonResponse({'success': False, 'error': 'This user is already in another family plan'}, status=400)

        # Create pending invitation for existing user
        try:
            family_member = FamilyMember.objects.create(
                admin=request.user,
                member=member_user,
                role='member',
                status='pending'
            )

            # Send invitation email
            accept_url = request.build_absolute_uri(
                reverse('accounts:accept_family_invitation', args=[family_member.id])
            )

            admin_name = request.user.get_full_name() or request.user.email

            send_mail(
                subject=f'[Reflekt] {admin_name} invited you to their Family Plan',
                message=f"""Hi {member_user.get_full_name() or member_user.email},

{admin_name} ({request.user.email}) has invited you to join their Reflekt Family Plan!

What happens when you accept:
• You'll get FREE premium access to all Reflekt features
• If you currently have a paid subscription, it will be cancelled and you won't be charged next month (no refund for the current period)
• You and {admin_name} will automatically become friends on Reflekt

Accept invitation: {accept_url}

This invitation is only valid for your account ({member_user.email}).

If you don't want to join, you can safely ignore this email.

Happy journaling!
The Reflekt Team
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            return JsonResponse({
                'success': True,
                'message': f'Invitation sent to {email}. They need to accept to join your family plan.',
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    else:
        # User doesn't exist - send signup invitation
        try:
            # Check if invitation already sent
            if Invitation.objects.filter(
                sender=request.user,
                email=email,
                status='pending'
            ).exists():
                return JsonResponse({'success': False, 'error': 'Invitation already sent to this email'}, status=400)

            # Create invitation with family plan context
            invitation = Invitation.objects.create(
                sender=request.user,
                email=email,
                status='pending',
                message=f"Join me on Reflekt with free premium access through my Family Plan!"
            )

            # Send signup invitation email
            signup_url = request.build_absolute_uri('/accounts/signup/')
            admin_name = request.user.get_full_name() or request.user.email

            send_mail(
                subject=f'[Reflekt] {admin_name} invited you to join Reflekt Family Plan',
                message=f"""Hi there!

{admin_name} ({request.user.email}) has invited you to join Reflekt with FREE premium access through their Family Plan!

Reflekt is a journaling app that helps you:
• Track your thoughts and feelings
• Discover patterns in your mood
• Set and achieve your goals
• Build positive habits

What you get with the Family Plan:
• FREE premium access to all features
• Automatic friend connection with {admin_name}
• No payment required!

Get started: {signup_url}

After creating your account with this email ({email}), you'll automatically be added to the family plan.

Happy journaling!
The Reflekt Team
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            return JsonResponse({
                'success': True,
                'message': f'Invitation sent to {email}. Once they sign up, they\'ll automatically join your family plan.',
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def accept_family_invitation(request, invitation_id):
    """Accept a family plan invitation."""
    from .models import FamilyMember, FriendRequest
    import stripe
    from django.conf import settings

    try:
        family_member = FamilyMember.objects.get(
            id=invitation_id,
            member=request.user,
            status='pending'
        )
    except FamilyMember.DoesNotExist:
        messages.error(request, 'Invitation not found or already processed.')
        return redirect('accounts:profile')

    try:
        # Cancel existing subscription if user has one
        profile = request.user.profile
        if profile.stripe_subscription_id:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                # Cancel at period end (no refund)
                subscription = stripe.Subscription.modify(
                    profile.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                messages.info(request, 'Your current subscription will be cancelled at the end of the billing period. No refunds will be issued.')
            except stripe.error.StripeError:
                # If subscription doesn't exist or already cancelled, continue
                pass

        # Accept the invitation
        family_member.status = 'active'
        family_member.save()

        # Upgrade to premium through family plan
        profile.subscription_tier = 'premium'
        profile.save()

        # Automatically add as friends
        admin = family_member.admin

        # Check if already friends
        from .models import Friendship
        if not Friendship.objects.filter(
            models.Q(user1=request.user, user2=admin) |
            models.Q(user1=admin, user2=request.user)
        ).exists():
            # Check if friend request already exists
            if not FriendRequest.objects.filter(
                models.Q(sender=request.user, recipient=admin) |
                models.Q(sender=admin, recipient=request.user),
                status='pending'
            ).exists():
                # Create friendship directly
                Friendship.objects.create(
                    user1=request.user,
                    user2=admin
                )

        admin_name = admin.get_full_name() or admin.email
        messages.success(request, f'🎉 Welcome to {admin_name}\'s family plan! You now have premium access and are friends with {admin_name}.')

        return redirect('analytics:dashboard')

    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('accounts:profile')


@login_required
def decline_family_invitation(request, invitation_id):
    """Decline a family plan invitation."""
    from .models import FamilyMember

    try:
        family_member = FamilyMember.objects.get(
            id=invitation_id,
            member=request.user,
            status='pending'
        )

        # Remove the invitation
        admin_name = family_member.admin.get_full_name() or family_member.admin.email
        family_member.delete()

        messages.info(request, f'You declined the family plan invitation from {admin_name}.')
        return redirect('accounts:profile')

    except FamilyMember.DoesNotExist:
        messages.error(request, 'Invitation not found or already processed.')
        return redirect('accounts:profile')


# =============================================================================
# Legal Pages
# =============================================================================

def privacy_policy(request):
    """Privacy policy page."""
    return render(request, 'legal/privacy_policy.html')


def terms_of_service(request):
    """Terms of service page."""
    return render(request, 'legal/terms_of_service.html')
