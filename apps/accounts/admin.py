from django.contrib import admin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import (Profile, Friendship, FriendRequest, Invitation,
                     Payment, SubscriptionHistory)


# Inline Profile in User Admin
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('subscription_tier', 'username', 'city', 'country_code', 'birthday',
              'horoscope_enabled', 'timezone', 'editor_preference', 'total_entries',
              'current_streak', 'longest_streak', 'last_entry_date')
    readonly_fields = ('total_entries', 'current_streak', 'longest_streak', 'last_entry_date')


# Customize User Admin
class CustomUserAdmin(admin.ModelAdmin):
    inlines = (ProfileInline,)
    list_display = ('email', 'subscription_tier_badge', 'date_joined', 'last_login',
                    'total_entries_count', 'is_staff', 'is_active')
    list_filter = ('profile__subscription_tier', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'profile__username')
    ordering = ('-date_joined',)
    actions = ['upgrade_to_premium', 'downgrade_to_free']

    def subscription_tier_badge(self, obj):
        if hasattr(obj, 'profile'):
            tier = obj.profile.subscription_tier
            if tier == 'premium':
                return format_html(
                    '<span style="background-color: #f59e0b; color: white; padding: 3px 8px; '
                    'border-radius: 3px; font-weight: bold;">⭐ PREMIUM</span>'
                )
            else:
                return format_html(
                    '<span style="background-color: #6b7280; color: white; padding: 3px 8px; '
                    'border-radius: 3px;">FREE</span>'
                )
        return '-'
    subscription_tier_badge.short_description = 'Subscription'

    def total_entries_count(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.total_entries
        return 0
    total_entries_count.short_description = 'Entries'
    total_entries_count.admin_order_field = 'profile__total_entries'

    def upgrade_to_premium(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.subscription_tier = 'premium'
                user.profile.save()
                count += 1
        self.message_user(request, f'{count} user(s) upgraded to Premium.')
    upgrade_to_premium.short_description = '⭐ Upgrade selected users to Premium'

    def downgrade_to_free(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.subscription_tier = 'free'
                user.profile.save()
                count += 1
        self.message_user(request, f'{count} user(s) downgraded to Free.')
    downgrade_to_free.short_description = '⬇️ Downgrade selected users to Free'


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'username', 'subscription_tier_badge', 'timezone',
                    'total_entries', 'current_streak', 'created_at')
    search_fields = ('user__email', 'username')
    readonly_fields = ('created_at', 'updated_at', 'total_entries', 'current_streak',
                       'longest_streak', 'last_entry_date')
    list_filter = ('subscription_tier', 'timezone', 'editor_preference', 'horoscope_enabled')
    actions = ['upgrade_to_premium', 'downgrade_to_free']

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'username')
        }),
        ('Subscription', {
            'fields': ('subscription_tier',),
            'description': 'Manage user subscription tier'
        }),
        ('Preferences', {
            'fields': ('timezone', 'editor_preference')
        }),
        ('Location & Horoscope', {
            'fields': ('city', 'country_code', 'birthday', 'horoscope_enabled')
        }),
        ('Stats', {
            'fields': ('total_entries', 'current_streak', 'longest_streak', 'last_entry_date'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'

    def subscription_tier_badge(self, obj):
        if obj.subscription_tier == 'premium':
            return format_html(
                '<span style="background-color: #f59e0b; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-weight: bold;">⭐ PREMIUM</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #6b7280; color: white; padding: 3px 8px; '
                'border-radius: 3px;">FREE</span>'
            )
    subscription_tier_badge.short_description = 'Tier'

    def upgrade_to_premium(self, request, queryset):
        count = queryset.update(subscription_tier='premium')
        self.message_user(request, f'{count} profile(s) upgraded to Premium.')
    upgrade_to_premium.short_description = '⭐ Upgrade to Premium'

    def downgrade_to_free(self, request, queryset):
        count = queryset.update(subscription_tier='free')
        self.message_user(request, f'{count} profile(s) downgraded to Free.')
    downgrade_to_free.short_description = '⬇️ Downgrade to Free'


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('user1', 'user2', 'created_at')
    search_fields = ('user1__email', 'user2__email', 'user1__profile__username', 'user2__profile__username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'status', 'created_at', 'responded_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__email', 'recipient__email')
    readonly_fields = ('created_at', 'responded_at')
    date_hierarchy = 'created_at'
    raw_id_fields = ('sender', 'recipient')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('sender', 'email', 'status', 'recipient', 'created_at', 'expires_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__email', 'email', 'recipient__email')
    readonly_fields = ('token', 'created_at', 'email_sent_at')
    date_hierarchy = 'created_at'
    raw_id_fields = ('sender', 'recipient')


# =============================================================================
# Payment & Subscription Admin
# =============================================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'amount_display', 'status_badge', 'payment_method',
                    'period_display', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__email', 'stripe_payment_intent_id', 'stripe_customer_id')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user',)
    actions = ['mark_as_completed', 'mark_as_failed', 'mark_as_refunded']

    fieldsets = (
        ('Payment Information', {
            'fields': ('user', 'amount', 'status', 'payment_method')
        }),
        ('Stripe Details', {
            'fields': ('stripe_payment_intent_id', 'stripe_customer_id'),
            'classes': ('collapse',)
        }),
        ('Subscription Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {
            'completed': '#22c55e',
            'pending': '#f59e0b',
            'failed': '#ef4444',
            'refunded': '#6b7280',
            'cancelled': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def period_display(self, obj):
        if obj.period_start and obj.period_end:
            return f"{obj.period_start} → {obj.period_end}"
        return '-'
    period_display.short_description = 'Period'

    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{count} payment(s) marked as completed.')
    mark_as_completed.short_description = '✅ Mark as Completed'

    def mark_as_failed(self, request, queryset):
        count = queryset.update(status='failed')
        self.message_user(request, f'{count} payment(s) marked as failed.')
    mark_as_failed.short_description = '❌ Mark as Failed'

    def mark_as_refunded(self, request, queryset):
        count = queryset.update(status='refunded')
        self.message_user(request, f'{count} payment(s) marked as refunded.')
    mark_as_refunded.short_description = '↩️ Mark as Refunded'


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'tier_change_display', 'change_type_badge',
                    'changed_by', 'created_at')
    list_filter = ('change_type', 'created_at', 'from_tier', 'to_tier')
    search_fields = ('user__email', 'notes')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    raw_id_fields = ('user', 'changed_by')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def tier_change_display(self, obj):
        return f"{obj.from_tier} → {obj.to_tier}"
    tier_change_display.short_description = 'Tier Change'

    def change_type_badge(self, obj):
        colors = {
            'upgrade': '#22c55e',
            'manual_upgrade': '#3b82f6',
            'downgrade': '#ef4444',
            'manual_downgrade': '#f59e0b',
            'payment_failed': '#dc2626',
        }
        color = colors.get(obj.change_type, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 0.75rem;">{}</span>',
            color, obj.get_change_type_display()
        )
    change_type_badge.short_description = 'Type'
