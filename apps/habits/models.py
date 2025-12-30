from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta


class Habit(models.Model):
    """
    Habit model with flexible frequency tracking.

    Supports:
    - Daily habits
    - Weekly habits (once per week)
    - X times per week (e.g., 3 times per week)
    - Specific days (e.g., Mon, Wed, Fri)
    """

    FREQUENCY_CHOICES = [
        ('daily', 'Every Day'),
        ('weekly', 'Once per Week'),
        ('x_per_week', 'X Times per Week'),
        ('specific_days', 'Specific Days'),
    ]

    CATEGORY_CHOICES = [
        ('health', 'Health & Fitness'),
        ('mindfulness', 'Mindfulness'),
        ('productivity', 'Productivity'),
        ('learning', 'Learning'),
        ('social', 'Social'),
        ('creative', 'Creative'),
        ('self_care', 'Self Care'),
        ('other', 'Other'),
    ]

    # Owner (multi-tenant)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='habits'
    )

    # Basic info
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        default='bi-check-circle',
        help_text="Bootstrap icon class (e.g., bi-heart, bi-book)"
    )
    color = models.CharField(
        max_length=7,
        default='#4f46e5',
        help_text="Hex color code"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other'
    )

    # Frequency settings
    frequency_type = models.CharField(
        max_length=15,
        choices=FREQUENCY_CHOICES,
        default='daily'
    )
    times_per_week = models.PositiveIntegerField(
        default=1,
        help_text="Number of times per week (for x_per_week frequency)"
    )
    specific_days = models.CharField(
        max_length=20,
        blank=True,
        help_text="Comma-separated day numbers: 0=Mon, 1=Tue, ..., 6=Sun"
    )

    # Tracking
    start_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    # Streak stats (denormalized for performance)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    last_completed_date = models.DateField(null=True, blank=True)

    # Journal integration
    journal_entries = models.ManyToManyField(
        'journal.Entry',
        related_name='linked_habits',
        blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'category']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('habits:habit_detail', kwargs={'pk': self.pk})

    @property
    def category_icon(self):
        """Return Bootstrap icon class for category."""
        icons = {
            'health': 'bi-heart-pulse',
            'mindfulness': 'bi-peace',
            'productivity': 'bi-lightning-charge',
            'learning': 'bi-book',
            'social': 'bi-people',
            'creative': 'bi-palette',
            'self_care': 'bi-flower1',
            'other': 'bi-check-circle',
        }
        return icons.get(self.category, 'bi-check-circle')

    @property
    def frequency_display(self):
        """Human-readable frequency description."""
        if self.frequency_type == 'daily':
            return 'Every day'
        elif self.frequency_type == 'weekly':
            return 'Once per week'
        elif self.frequency_type == 'x_per_week':
            return f'{self.times_per_week}x per week'
        elif self.frequency_type == 'specific_days':
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            day_nums = [int(d) for d in self.specific_days.split(',') if d]
            day_names = [days[d] for d in day_nums if 0 <= d <= 6]
            return ', '.join(day_names)
        return ''

    def is_due_on_date(self, date):
        """Check if this habit is due on the given date."""
        if date < self.start_date:
            return False

        if self.frequency_type == 'daily':
            return True
        elif self.frequency_type == 'weekly':
            # Due once per week - consider due on Monday or any day not yet completed that week
            week_start = date - timedelta(days=date.weekday())
            week_end = week_start + timedelta(days=6)
            completed_this_week = self.checkins.filter(
                check_date__gte=week_start,
                check_date__lte=week_end,
                completed=True
            ).exists()
            return not completed_this_week
        elif self.frequency_type == 'x_per_week':
            # Due if not yet completed X times this week
            week_start = date - timedelta(days=date.weekday())
            week_end = week_start + timedelta(days=6)
            completions_this_week = self.checkins.filter(
                check_date__gte=week_start,
                check_date__lte=week_end,
                completed=True
            ).count()
            return completions_this_week < self.times_per_week
        elif self.frequency_type == 'specific_days':
            # Due only on specific days of the week
            day_nums = [int(d) for d in self.specific_days.split(',') if d]
            return date.weekday() in day_nums
        return False

    def is_completed_on_date(self, date):
        """Check if habit was completed on the given date."""
        return self.checkins.filter(check_date=date, completed=True).exists()

    def get_completion_rate(self, days=30):
        """Calculate completion rate over the last N days."""
        today = timezone.now().date()
        start = today - timedelta(days=days)

        due_count = 0
        completed_count = 0

        for i in range(days + 1):
            check_date = start + timedelta(days=i)
            if self.is_due_on_date(check_date):
                due_count += 1
                if self.is_completed_on_date(check_date):
                    completed_count += 1

        if due_count == 0:
            return 100  # No due dates = 100% completion
        return (completed_count / due_count) * 100

    def update_streak_stats(self):
        """Update streak statistics based on checkins."""
        today = timezone.now().date()
        streak = 0
        check_date = today

        # Count backwards from today to find current streak
        while True:
            if not self.is_due_on_date(check_date):
                check_date -= timedelta(days=1)
                if check_date < self.start_date:
                    break
                continue

            if self.is_completed_on_date(check_date):
                streak += 1
                check_date -= timedelta(days=1)
                if check_date < self.start_date:
                    break
            else:
                # Streak broken if not today (give grace for today)
                if check_date != today:
                    break
                check_date -= timedelta(days=1)
                if check_date < self.start_date:
                    break

        self.current_streak = streak

        # Calculate longest streak from all historical data
        longest = self._calculate_longest_streak()
        self.longest_streak = max(streak, longest)

        # Update total completions
        self.total_completions = self.checkins.filter(completed=True).count()

        # Update last completed date
        last_checkin = self.checkins.filter(completed=True).order_by('-check_date').first()
        self.last_completed_date = last_checkin.check_date if last_checkin else None

        self.save(update_fields=['current_streak', 'longest_streak', 'total_completions', 'last_completed_date'])

    def _calculate_longest_streak(self):
        """Calculate the longest streak from all historical check-ins."""
        # Get all completed check-in dates as a set for O(1) lookup
        completed_dates = set(
            self.checkins.filter(completed=True)
            .values_list('check_date', flat=True)
        )

        if not completed_dates:
            return 0

        # Start from the earliest check-in, not start_date (in case of pre-existing data)
        earliest_checkin = min(completed_dates)
        latest_checkin = max(completed_dates)

        longest_streak = 0
        current_streak = 0

        # For daily habits, simply count consecutive days
        if self.frequency_type == 'daily':
            check_date = earliest_checkin
            while check_date <= latest_checkin:
                if check_date in completed_dates:
                    current_streak += 1
                    longest_streak = max(longest_streak, current_streak)
                else:
                    current_streak = 0
                check_date += timedelta(days=1)
        else:
            # For other frequencies, use is_due_on_date logic
            # But start from earliest checkin date
            check_date = earliest_checkin
            while check_date <= latest_checkin:
                # For non-daily, check if it was a due date
                if self._is_due_on_date_ignoring_start(check_date):
                    if check_date in completed_dates:
                        current_streak += 1
                        longest_streak = max(longest_streak, current_streak)
                    else:
                        current_streak = 0
                check_date += timedelta(days=1)

        return longest_streak

    def _is_due_on_date_ignoring_start(self, date):
        """Check if habit would be due on date, ignoring start_date constraint."""
        if self.frequency_type == 'daily':
            return True
        elif self.frequency_type == 'specific_days':
            day_nums = [int(d) for d in self.specific_days.split(',') if d]
            return date.weekday() in day_nums
        # For weekly/x_per_week, treat as daily for streak purposes
        return True


class HabitCheckin(models.Model):
    """
    Daily check-in record for a habit.
    """
    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name='checkins'
    )
    check_date = models.DateField(default=timezone.now)
    completed = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    # Optional link to journal entry
    journal_entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='habit_checkins'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['habit', 'check_date']
        ordering = ['-check_date']

    def __str__(self):
        status = "completed" if self.completed else "missed"
        return f"{self.habit.name} - {self.check_date} ({status})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update habit streak stats
        self.habit.update_streak_stats()
