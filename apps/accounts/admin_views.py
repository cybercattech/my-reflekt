"""
Custom admin dashboard views for subscription management.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Sum, Q
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Profile, Payment, SubscriptionHistory


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
    }

    return render(request, 'admin/subscription_dashboard.html', context)
