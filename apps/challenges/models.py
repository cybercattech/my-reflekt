"""
Models for the Challenges app.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


class Challenge(models.Model):
    """
    A structured journaling challenge with prompts and cadence.
    """
    CADENCE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]

    TIER_CHOICES = [
        ('challenge', 'Challenge'),
        ('challenge_bronze', 'Challenge Bronze'),
        ('challenge_silver', 'Challenge Silver'),
        ('challenge_gold', 'Challenge Gold'),
    ]

    # Basic info
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)

    # Visual
    icon = models.CharField(max_length=50, default='bi-trophy', help_text="Bootstrap icon class")
    color = models.CharField(max_length=7, default='#6366f1', help_text="Hex color for challenge theme")
    cover_image = models.URLField(blank=True, help_text="URL to cover image")

    # Cadence
    cadence = models.CharField(max_length=10, choices=CADENCE_CHOICES, default='daily')
    duration_days = models.PositiveIntegerField(help_text="Total number of prompts/days")

    # Related content (optional)
    blog_post = models.ForeignKey(
        'blog.Post',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='challenges',
        help_text="Optional blog post providing context"
    )

    # Badge reward
    badge_id = models.CharField(max_length=50, unique=True, help_text="Unique badge ID for completion")
    badge_name = models.CharField(max_length=100, help_text="Badge display name")
    badge_icon = models.CharField(max_length=50, default='bi-award')
    badge_tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='challenge')

    # Status and availability
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    requires_premium = models.BooleanField(default=False)

    # Stats (denormalized for performance)
    participant_count = models.PositiveIntegerField(default=0)
    completion_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Challenge.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('challenges:detail', kwargs={'slug': self.slug})

    @property
    def completion_rate(self):
        """Calculate completion rate percentage."""
        if self.participant_count == 0:
            return 0
        return int((self.completion_count / self.participant_count) * 100)


class ChallengePrompt(models.Model):
    """
    Individual prompt within a challenge.
    For a 7-day daily challenge, there would be 7 prompts.
    """
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name='prompts'
    )
    day_number = models.PositiveIntegerField(help_text="Day/prompt number (1, 2, 3, etc.)")
    title = models.CharField(max_length=200)
    prompt_text = models.TextField(help_text="The journal prompt for this day")
    guidance = models.TextField(blank=True, help_text="Optional additional guidance or tips")
    icon = models.CharField(max_length=50, default='bi-journal-text')

    class Meta:
        ordering = ['challenge', 'day_number']
        unique_together = ['challenge', 'day_number']

    def __str__(self):
        return f"{self.challenge.title} - Day {self.day_number}: {self.title}"


class UserChallenge(models.Model):
    """
    Tracks a user's participation in a challenge.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='challenge_participations'
    )
    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.CASCADE,
        related_name='participants'
    )

    # Dates
    started_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(help_text="The date user began the challenge")
    expected_end_date = models.DateField(help_text="Expected completion date based on cadence")
    completed_at = models.DateTimeField(null=True, blank=True)

    # Progress
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    current_day = models.PositiveIntegerField(default=1)
    prompts_completed = models.PositiveIntegerField(default=0)

    # Streak tracking for cadence enforcement
    last_entry_date = models.DateField(null=True, blank=True)
    missed_days = models.PositiveIntegerField(default=0)

    # Badge awarded?
    badge_earned = models.BooleanField(default=False)
    badge_earned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'challenge']
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['challenge', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.challenge.title} ({self.status})"

    @property
    def progress_percent(self):
        """Calculate progress as percentage."""
        total = self.challenge.prompts.count()
        if total == 0:
            return 0
        return int((self.prompts_completed / total) * 100)

    @property
    def days_remaining(self):
        """Calculate days remaining until expected end."""
        today = timezone.now().date()
        if today > self.expected_end_date:
            return 0
        return (self.expected_end_date - today).days


class ChallengeEntry(models.Model):
    """
    Links a journal entry to a specific challenge prompt.
    """
    user_challenge = models.ForeignKey(
        UserChallenge,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    prompt = models.ForeignKey(
        ChallengePrompt,
        on_delete=models.CASCADE,
        related_name='user_entries'
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.CASCADE,
        related_name='challenge_entries'
    )

    # Submission timing
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_on_time = models.BooleanField(default=True, help_text="Was this submitted within cadence?")

    class Meta:
        unique_together = ['user_challenge', 'prompt']
        ordering = ['prompt__day_number']

    def __str__(self):
        return f"{self.user_challenge.user.email} - {self.prompt}"
