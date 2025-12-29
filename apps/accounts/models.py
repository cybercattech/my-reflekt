import secrets
from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator, MinLengthValidator
from django.utils import timezone as django_timezone


class Profile(models.Model):
    """Extended user profile for Reflekt users."""
    EDITOR_CHOICES = [
        ('myst_markdown', 'MyST Markdown'),
        ('rich_text', 'Rich Text (Quill)'),
    ]

    TIER_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Username for friend discovery
    username = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]+$',
                message='Username can only contain letters, numbers, and underscores'
            ),
            MinLengthValidator(3),
        ],
        help_text="Your unique @username for friends to find you"
    )

    # Subscription
    subscription_tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free',
        help_text="User's subscription tier"
    )

    # Stripe Integration
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe customer ID")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe subscription ID")
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('canceled', 'Canceled'),
            ('past_due', 'Past Due'),
            ('incomplete', 'Incomplete'),
            ('trialing', 'Trialing'),
        ],
        blank=True,
        null=True,
        help_text="Stripe subscription status"
    )
    subscription_plan = models.CharField(
        max_length=50,
        choices=[
            ('individual_monthly', 'Individual - Monthly ($10/mo)'),
            ('individual_yearly', 'Individual - Yearly ($100/yr)'),
            ('family_monthly', 'Family - Monthly ($20/mo)'),
            ('family_yearly', 'Family - Yearly ($200/yr)'),
        ],
        blank=True,
        null=True,
        help_text="Selected subscription plan"
    )
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    # Preferences
    timezone = models.CharField(max_length=50, default='America/New_York')
    editor_preference = models.CharField(
        max_length=20,
        choices=EDITOR_CHOICES,
        default='myst_markdown'
    )

    # Location for weather tracking
    city = models.CharField(max_length=100, blank=True, help_text="City name for weather data")
    country_code = models.CharField(max_length=2, blank=True, default='US', help_text="Two-letter country code")

    # Horoscope settings
    birthday = models.DateField(null=True, blank=True, help_text="Birthday for zodiac sign calculation")
    horoscope_enabled = models.BooleanField(default=False, help_text="Enable horoscope-based insights")

    # Spiritual Reflection settings
    devotion_enabled = models.BooleanField(default=False, help_text="Enable daily Christian devotions")

    # Stats (denormalized for quick access)
    total_entries = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_entry_date = models.DateField(null=True, blank=True)

    # Legal Agreement Tracking
    terms_accepted = models.BooleanField(default=False, help_text="User accepted Terms of Service")
    terms_accepted_at = models.DateTimeField(null=True, blank=True, help_text="When terms were accepted")
    privacy_accepted = models.BooleanField(default=False, help_text="User accepted Privacy Policy")
    privacy_accepted_at = models.DateTimeField(null=True, blank=True, help_text="When privacy policy was accepted")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.email}"

    @property
    def display_name(self):
        """Return username or email for display."""
        return f"@{self.username}" if self.username else self.user.email

    @property
    def zodiac_display(self):
        """Return zodiac sign display name if birthday is set."""
        if not self.birthday:
            return None
        from apps.analytics.services.horoscope import get_zodiac_data
        data = get_zodiac_data(self.birthday)
        if data:
            return f"{data['symbol']} {data['display_name']}"
        return None

    @property
    def zodiac_sign(self):
        """Return zodiac sign name if birthday is set."""
        if not self.birthday:
            return None
        from apps.analytics.services.horoscope import get_zodiac_sign
        return get_zodiac_sign(self.birthday)

    @property
    def is_premium(self):
        """Check if user has premium subscription."""
        return self.subscription_tier == 'premium'

    @property
    def is_free(self):
        """Check if user is on free tier."""
        return self.subscription_tier == 'free'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a Profile when a new User is created."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save Profile when User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()


# =============================================================================
# Friend System Models
# =============================================================================

class Friendship(models.Model):
    """
    Bidirectional friendship relationship.

    Stores one record per friendship (user1.id < user2.id to avoid duplicates).
    Both users can see each other as friends.
    """
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friendships_as_user1'
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friendships_as_user2'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user1', 'user2']
        constraints = [
            models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F('user2_id')),
                name='friendship_user_ordering'
            )
        ]
        indexes = [
            models.Index(fields=['user1', 'created_at']),
            models.Index(fields=['user2', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user1.email} <-> {self.user2.email}"

    @classmethod
    def create_friendship(cls, user_a, user_b):
        """Create friendship with proper ordering."""
        if user_a.id > user_b.id:
            user_a, user_b = user_b, user_a
        return cls.objects.create(user1=user_a, user2=user_b)

    @classmethod
    def are_friends(cls, user_a, user_b):
        """Check if two users are friends."""
        if user_a.id > user_b.id:
            user_a, user_b = user_b, user_a
        return cls.objects.filter(user1=user_a, user2=user_b).exists()

    @classmethod
    def get_friends(cls, user):
        """Get all friends of a user."""
        from django.db.models import Q
        friendships = cls.objects.filter(Q(user1=user) | Q(user2=user))
        friends = []
        for f in friendships.select_related('user1', 'user2', 'user1__profile', 'user2__profile'):
            friends.append(f.user2 if f.user1 == user else f.user1)
        return friends


class FriendRequest(models.Model):
    """
    Pending friend request between existing users.

    Sender initiates, recipient can accept/deny.
    Sender can cancel before response.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('denied', 'Denied'),
        ('cancelled', 'Cancelled'),
    ]

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_friend_requests'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_friend_requests'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional message with request"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['sender', 'recipient']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['sender', 'status']),
        ]

    def __str__(self):
        return f"{self.sender.email} -> {self.recipient.email} ({self.status})"


class Invitation(models.Model):
    """
    Invitation sent to non-user email addresses.

    When invited person signs up, they see pending invitation
    and can accept/deny to create friendship.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),  # Not yet signed up
        ('signed_up', 'Signed Up'),  # Signed up, awaiting response
        ('accepted', 'Accepted'),
        ('denied', 'Denied'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    email = models.EmailField(
        help_text="Email address of invited person"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.CharField(
        max_length=200,
        blank=True,
        help_text="Personal message in invitation email"
    )

    # Set when invited person signs up
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_invitations'
    )

    # Tracking
    token = models.CharField(max_length=64, unique=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['sender', 'email']
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['token']),
            models.Index(fields=['recipient', 'status']),
        ]

    def __str__(self):
        return f"{self.sender.email} invited {self.email} ({self.status})"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return django_timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = django_timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)


# =============================================================================
# Family Plan Management
# =============================================================================

class FamilyMember(models.Model):
    """
    Track family plan memberships.

    The 'admin' is the person who pays for the family plan.
    'member' are people who get premium access through the family plan.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('removed', 'Removed'),
        ('pending', 'Pending Invitation'),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='family_members',
        help_text="The family plan admin/owner"
    )
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='family_memberships',
        help_text="The family member with access"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Admin is the account owner, members are family"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of family membership"
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True, help_text="When member was removed from family")
    removed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='removed_family_members',
        help_text="Who removed this member"
    )

    class Meta:
        unique_together = ['admin', 'member']
        indexes = [
            models.Index(fields=['admin', 'status']),
            models.Index(fields=['member', 'status']),
        ]

    def __str__(self):
        return f"{self.member.email} in {self.admin.email}'s family ({self.status})"

    @classmethod
    def get_active_members(cls, admin_user):
        """Get all active family members for an admin."""
        return cls.objects.filter(
            admin=admin_user,
            status='active'
        ).select_related('member', 'member__profile')

    @classmethod
    def get_family_admin(cls, member_user):
        """Get the family admin for a member, if any."""
        membership = cls.objects.filter(
            member=member_user,
            status='active'
        ).select_related('admin', 'admin__profile').first()
        return membership.admin if membership else None

    @classmethod
    def is_family_admin(cls, user):
        """Check if user is a family plan admin with active members."""
        return cls.objects.filter(admin=user, status='active').exists()

    @classmethod
    def count_active_members(cls, admin_user):
        """Count active family members (excluding admin themselves)."""
        return cls.objects.filter(admin=admin_user, status='active').exclude(member=admin_user).count()


# =============================================================================
# Subscription & Payment Models
# =============================================================================

class Payment(models.Model):
    """Track subscription payments."""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('manual', 'Manual'),
        ('comp', 'Complimentary'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount in USD"
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='stripe'
    )

    # Stripe-specific fields
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)

    # Period covered by this payment
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    # Notes for manual/comp payments
    notes = models.TextField(blank=True, help_text="Admin notes")

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['stripe_payment_intent_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - ${self.amount} ({self.status})"

    @property
    def is_successful(self):
        return self.status == 'completed'


class SubscriptionHistory(models.Model):
    """Track subscription tier changes."""
    CHANGE_TYPE_CHOICES = [
        ('upgrade', 'Upgraded to Premium'),
        ('downgrade', 'Downgraded to Free'),
        ('manual_upgrade', 'Manual Upgrade (Admin)'),
        ('manual_downgrade', 'Manual Downgrade (Admin)'),
        ('payment_failed', 'Downgrade (Payment Failed)'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscription_history'
    )
    from_tier = models.CharField(max_length=20)
    to_tier = models.CharField(max_length=20)
    change_type = models.CharField(
        max_length=30,
        choices=CHANGE_TYPE_CHOICES
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tier_changes_made',
        help_text="Admin user who made the change (if manual)"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Subscription histories'
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email}: {self.from_tier} → {self.to_tier}"
