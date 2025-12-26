from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone


class Goal(models.Model):
    """
    SMART Goal model for tracking personal objectives.

    - Specific: title, description
    - Measurable: success_criteria, target_value, current_value, unit
    - Achievable: why_achievable
    - Relevant: relevance
    - Time-bound: start_date, due_date
    """

    CATEGORY_CHOICES = [
        ('health', 'Health & Fitness'),
        ('career', 'Career & Professional'),
        ('education', 'Education & Learning'),
        ('finance', 'Finance & Money'),
        ('relationships', 'Relationships'),
        ('personal', 'Personal Development'),
        ('creative', 'Creative & Hobbies'),
        ('other', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('abandoned', 'Abandoned'),
    ]

    # Owner (multi-tenant)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='goals'
    )

    # Specific
    title = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text="Describe your goal in detail"
    )

    # Measurable
    success_criteria = models.TextField(
        blank=True,
        help_text="How will you know when this goal is achieved?"
    )
    target_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target number (e.g., 10 for '10 books')"
    )
    current_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Current progress value"
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unit of measurement (e.g., 'books', 'miles', 'pounds')"
    )

    # Achievable
    why_achievable = models.TextField(
        blank=True,
        help_text="Why is this goal achievable for you?"
    )

    # Relevant
    relevance = models.TextField(
        blank=True,
        help_text="Why is this goal important to you?"
    )

    # Time-bound
    start_date = models.DateField(default=timezone.now)
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="When do you want to achieve this goal?"
    )

    # Organization
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='personal'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='not_started'
    )

    # Journal integration
    journal_entries = models.ManyToManyField(
        'journal.Entry',
        related_name='linked_goals',
        blank=True
    )

    # Habit integration - link habits that support this goal
    linked_habits = models.ManyToManyField(
        'habits.Habit',
        related_name='linked_goals',
        blank=True,
        help_text="Habits that contribute to achieving this goal"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'category']),
            models.Index(fields=['user', 'due_date']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('goals:goal_detail', kwargs={'pk': self.pk})

    @property
    def progress_percentage(self):
        """Calculate progress based on target_value or milestones."""
        if self.target_value and self.target_value > 0:
            percentage = (float(self.current_value) / float(self.target_value)) * 100
            return min(percentage, 100)  # Cap at 100%

        # If no target value, calculate from milestones
        milestones = self.milestones.all()
        if milestones.exists():
            completed = milestones.filter(is_completed=True).count()
            return (completed / milestones.count()) * 100

        # No measurable progress
        if self.status == 'completed':
            return 100
        return 0

    @property
    def days_remaining(self):
        """Calculate days until due date."""
        if not self.due_date:
            return None
        delta = self.due_date - timezone.now().date()
        return delta.days

    @property
    def is_overdue(self):
        """Check if goal is past due date."""
        if not self.due_date:
            return False
        return timezone.now().date() > self.due_date and self.status not in ['completed', 'abandoned']

    @property
    def status_color(self):
        """Return Bootstrap color class for status."""
        colors = {
            'not_started': 'secondary',
            'in_progress': 'primary',
            'completed': 'success',
            'on_hold': 'warning',
            'abandoned': 'danger',
        }
        return colors.get(self.status, 'secondary')

    @property
    def priority_color(self):
        """Return Bootstrap color class for priority."""
        colors = {
            'low': 'info',
            'medium': 'warning',
            'high': 'danger',
        }
        return colors.get(self.priority, 'secondary')

    @property
    def category_icon(self):
        """Return Bootstrap icon class for category."""
        icons = {
            'health': 'bi-heart-pulse',
            'career': 'bi-briefcase',
            'education': 'bi-book',
            'finance': 'bi-currency-dollar',
            'relationships': 'bi-people',
            'personal': 'bi-person-check',
            'creative': 'bi-palette',
            'other': 'bi-bullseye',
        }
        return icons.get(self.category, 'bi-bullseye')


class Milestone(models.Model):
    """
    Sub-goals or checkpoints within a goal.
    """
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)

    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.goal.title} - {self.title}"

    def toggle_complete(self):
        """Toggle completion status."""
        self.is_completed = not self.is_completed
        if self.is_completed:
            self.completed_at = timezone.now()
        else:
            self.completed_at = None
        self.save()


class GoalProgressLog(models.Model):
    """
    Track progress updates for a goal over time.
    """
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='progress_logs'
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="New progress value"
    )
    note = models.TextField(
        blank=True,
        help_text="Optional note about this progress update"
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']

    def __str__(self):
        return f"{self.goal.title}: {self.value} ({self.logged_at.date()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the goal's current value
        self.goal.current_value = self.value
        self.goal.save(update_fields=['current_value', 'updated_at'])
