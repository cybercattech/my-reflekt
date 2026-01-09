"""
Wellness tracking models for pain, intimacy, cycle tracking, and body fitness.
"""
from datetime import date
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PainLog(models.Model):
    """Track pain episodes with location, intensity, and type."""

    LOCATION_CHOICES = [
        ('head', 'Head'),
        ('neck', 'Neck'),
        ('back', 'Back'),
        ('chest', 'Chest'),
        ('arm', 'Arm'),
        ('leg', 'Leg'),
        ('tooth', 'Tooth'),
        ('stomach', 'Stomach'),
        ('joint', 'Joint'),
        ('other', 'Other'),
    ]

    PAIN_TYPE_CHOICES = [
        ('sharp', 'Sharp'),
        ('dull', 'Dull'),
        ('throbbing', 'Throbbing'),
        ('burning', 'Burning'),
        ('aching', 'Aching'),
        ('stabbing', 'Stabbing'),
    ]

    DURATION_CHOICES = [
        ('brief', 'Brief (minutes)'),
        ('hours', 'Hours'),
        ('all_day', 'All Day'),
        ('ongoing', 'Ongoing'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pain_logs'
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pain_logs',
        help_text="Optional linked journal entry"
    )
    logged_at = models.DateTimeField(default=timezone.now)
    location = models.CharField(max_length=50, choices=LOCATION_CHOICES)
    intensity = models.PositiveSmallIntegerField(
        help_text="Pain intensity from 1-10"
    )
    pain_type = models.CharField(
        max_length=30,
        choices=PAIN_TYPE_CHOICES,
        blank=True
    )
    duration = models.CharField(
        max_length=20,
        choices=DURATION_CHOICES,
        blank=True
    )
    notes = models.TextField(blank=True)
    triggers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of suspected triggers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['user', '-logged_at']),
            models.Index(fields=['user', 'location']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.location} ({self.intensity}/10) on {self.logged_at.date()}"

    @property
    def intensity_label(self):
        """Return descriptive label for pain intensity."""
        if self.intensity <= 2:
            return 'Mild'
        elif self.intensity <= 4:
            return 'Moderate'
        elif self.intensity <= 6:
            return 'Significant'
        elif self.intensity <= 8:
            return 'Severe'
        else:
            return 'Extreme'

    @property
    def location_display(self):
        """Return display name for location."""
        return dict(self.LOCATION_CHOICES).get(self.location, self.location.title())

    @property
    def icon(self):
        """Return Bootstrap icon for pain location."""
        icons = {
            'head': 'bi-emoji-dizzy',
            'neck': 'bi-person',
            'back': 'bi-person-arms-up',
            'chest': 'bi-heart-pulse',
            'arm': 'bi-hand-index',
            'leg': 'bi-person-walking',
            'tooth': 'bi-emoji-grimace',
            'stomach': 'bi-activity',
            'joint': 'bi-link-45deg',
            'other': 'bi-bandaid',
        }
        return icons.get(self.location, 'bi-bandaid')


class IntimacyLog(models.Model):
    """Discreet tracking for intimate moments."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='intimacy_logs'
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='intimacy_logs'
    )
    logged_at = models.DateTimeField(default=timezone.now)
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional rating 1-5"
    )
    partner = models.ForeignKey(
        'accounts.FamilyMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='intimacy_logs'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['user', '-logged_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - 🍀 on {self.logged_at.date()}"


class CycleLog(models.Model):
    """Track menstrual cycle events and symptoms."""

    EVENT_TYPE_CHOICES = [
        ('period_start', 'Period Started'),
        ('period_end', 'Period Ended'),
        ('symptom', 'Symptom Only'),
        ('note', 'Note'),
    ]

    FLOW_LEVEL_CHOICES = [
        ('light', 'Light'),
        ('medium', 'Medium'),
        ('heavy', 'Heavy'),
    ]

    SYMPTOM_CHOICES = [
        ('cramps', 'Cramps'),
        ('bloating', 'Bloating'),
        ('headache', 'Headache'),
        ('fatigue', 'Fatigue'),
        ('mood_swings', 'Mood Swings'),
        ('breast_tenderness', 'Breast Tenderness'),
        ('hot_flash', 'Hot Flash'),
        ('night_sweats', 'Night Sweats'),
        ('acne', 'Acne'),
        ('cravings', 'Cravings'),
        ('nausea', 'Nausea'),
        ('back_pain', 'Back Pain'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cycle_logs'
    )
    person = models.ForeignKey(
        'accounts.FamilyMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cycle_logs',
        help_text="Track for self (null) or family member"
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cycle_logs'
    )
    log_date = models.DateField(default=timezone.now)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    flow_level = models.CharField(
        max_length=10,
        choices=FLOW_LEVEL_CHOICES,
        blank=True
    )
    symptoms = models.JSONField(
        default=list,
        blank=True,
        help_text="List of symptoms"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-log_date']
        indexes = [
            models.Index(fields=['user', '-log_date']),
            models.Index(fields=['user', 'person', '-log_date']),
            models.Index(fields=['user', 'event_type']),
        ]

    def __str__(self):
        person_name = self.person.name if self.person else "Self"
        return f"{self.user.email} - {person_name} - {self.event_type} on {self.log_date}"

    @property
    def event_display(self):
        """Return display name for event type."""
        return dict(self.EVENT_TYPE_CHOICES).get(self.event_type, self.event_type)

    @property
    def symptoms_display(self):
        """Return formatted symptom list."""
        symptom_dict = dict(self.SYMPTOM_CHOICES)
        return [symptom_dict.get(s, s.replace('_', ' ').title()) for s in self.symptoms]


class CyclePrediction(models.Model):
    """Computed cycle predictions based on historical data."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cycle_predictions'
    )
    person = models.ForeignKey(
        'accounts.FamilyMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cycle_predictions'
    )
    predicted_start = models.DateField(
        help_text="Next predicted period start date"
    )
    avg_cycle_length = models.PositiveSmallIntegerField(
        default=28,
        help_text="Average cycle length in days"
    )
    avg_period_length = models.PositiveSmallIntegerField(
        default=5,
        help_text="Average period length in days"
    )
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'person']

    def __str__(self):
        person_name = self.person.name if self.person else "Self"
        return f"{self.user.email} - {person_name} - Next: {self.predicted_start}"


# =============================================================================
# Body Fitness Tracking Models
# =============================================================================

class BodyMetric(models.Model):
    """Track weight and body measurements over time."""

    WEIGHT_UNIT_CHOICES = [
        ('lbs', 'Pounds'),
        ('kg', 'Kilograms'),
    ]

    MEASUREMENT_UNIT_CHOICES = [
        ('in', 'Inches'),
        ('cm', 'Centimeters'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='body_metrics'
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='body_metrics',
        help_text="Optional linked journal entry"
    )
    logged_at = models.DateTimeField(default=timezone.now)

    # Weight
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Weight in selected unit"
    )
    weight_unit = models.CharField(
        max_length=3,
        choices=WEIGHT_UNIT_CHOICES,
        default='lbs'
    )

    # Body measurements (stored in inches by default)
    waist = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Waist at navel"
    )
    chest = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )
    biceps = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )
    thighs = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )
    hips = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )
    body_fat = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Body fat percentage"
    )
    measurement_unit = models.CharField(
        max_length=2,
        choices=MEASUREMENT_UNIT_CHOICES,
        default='in'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['user', '-logged_at']),
        ]

    def __str__(self):
        weight_str = f"{self.weight} {self.weight_unit}" if self.weight else "No weight"
        return f"{self.user.email} - {weight_str} on {self.logged_at.date()}"

    @property
    def weight_in_lbs(self):
        """Return weight converted to pounds."""
        if not self.weight:
            return None
        if self.weight_unit == 'kg':
            return self.weight * Decimal('2.20462')
        return self.weight

    @property
    def weight_in_kg(self):
        """Return weight converted to kilograms."""
        if not self.weight:
            return None
        if self.weight_unit == 'lbs':
            return self.weight / Decimal('2.20462')
        return self.weight

    def get_measurement(self, field_name, unit='in'):
        """Get measurement in specified unit."""
        value = getattr(self, field_name, None)
        if value is None:
            return None
        if unit == 'cm' and self.measurement_unit == 'in':
            return value * Decimal('2.54')
        elif unit == 'in' and self.measurement_unit == 'cm':
            return value / Decimal('2.54')
        return value


class CardioLog(models.Model):
    """Track cardio activities like running, walking, cycling."""

    ACTIVITY_TYPE_CHOICES = [
        ('run', 'Running'),
        ('walk', 'Walking'),
        ('bike', 'Cycling'),
        ('swim', 'Swimming'),
        ('elliptical', 'Elliptical'),
        ('rowing', 'Rowing'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cardio_logs'
    )
    entry = models.ForeignKey(
        'journal.Entry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cardio_logs',
        help_text="Optional linked journal entry"
    )
    logged_at = models.DateTimeField(default=timezone.now)
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPE_CHOICES,
        default='run'
    )

    distance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Distance in miles"
    )
    duration_minutes = models.PositiveIntegerField(
        help_text="Total minutes"
    )
    duration_seconds = models.PositiveSmallIntegerField(
        default=0,
        help_text="Additional seconds (0-59)"
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['user', '-logged_at']),
            models.Index(fields=['user', 'activity_type', '-logged_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.activity_type} {self.distance}mi in {self.duration_display}"

    @property
    def total_seconds(self):
        """Get total duration in seconds."""
        return (self.duration_minutes * 60) + self.duration_seconds

    @property
    def total_minutes_decimal(self):
        """Get total duration as decimal minutes."""
        return self.duration_minutes + (self.duration_seconds / 60)

    @property
    def duration_display(self):
        """Return formatted duration string (MM:SS)."""
        return f"{self.duration_minutes}:{self.duration_seconds:02d}"

    @property
    def pace(self):
        """Calculate pace in minutes per mile."""
        if not self.distance or self.distance == 0:
            return None
        total_minutes = self.total_minutes_decimal
        return total_minutes / float(self.distance)

    @property
    def pace_display(self):
        """Return formatted pace string (MM:SS per mile)."""
        if self.pace is None:
            return "N/A"
        minutes = int(self.pace)
        seconds = int((self.pace - minutes) * 60)
        return f"{minutes}:{seconds:02d}/mi"

    @property
    def activity_display(self):
        """Return display name for activity type."""
        return dict(self.ACTIVITY_TYPE_CHOICES).get(self.activity_type, self.activity_type.title())

    @property
    def icon(self):
        """Return Bootstrap icon for activity type."""
        icons = {
            'run': 'bi-person-walking',
            'walk': 'bi-person',
            'bike': 'bi-bicycle',
            'swim': 'bi-water',
            'elliptical': 'bi-arrow-repeat',
            'rowing': 'bi-arrows-expand',
            'other': 'bi-activity',
        }
        return icons.get(self.activity_type, 'bi-activity')


class FitnessGoal(models.Model):
    """Specific fitness goals with schedule tracking and progress monitoring."""

    GOAL_TYPE_CHOICES = [
        ('weight', 'Weight Goal'),
        ('measurement', 'Measurement Goal'),
        ('cardio', 'Cardio Goal'),
        ('cardio_time', 'Cardio Time Goal'),  # Legacy
        ('cardio_distance', 'Cardio Distance Goal'),  # Legacy
    ]

    MEASUREMENT_TYPE_CHOICES = [
        ('weight', 'Weight'),
        ('waist', 'Waist'),
        ('chest', 'Chest'),
        ('biceps', 'Biceps'),
        ('thighs', 'Thighs'),
        ('hips', 'Hips'),
        ('body_fat', 'Body Fat %'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='fitness_goals'
    )
    title = models.CharField(max_length=200)
    goal_type = models.CharField(
        max_length=20,
        choices=GOAL_TYPE_CHOICES
    )
    measurement_type = models.CharField(
        max_length=20,
        choices=MEASUREMENT_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="For weight/measurement goals"
    )

    # For cardio goals
    activity_type = models.CharField(
        max_length=20,
        choices=CardioLog.ACTIVITY_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="For cardio goals"
    )
    target_distance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target distance (e.g., 3 miles)"
    )
    target_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Target time in minutes (e.g., 26 for 26:00)"
    )
    target_time_seconds = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text="Target time seconds (0-59)"
    )

    # Target values
    start_value = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Starting value when goal was created"
    )
    target_value = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Target value to achieve"
    )
    current_value = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Most recent recorded value"
    )
    unit = models.CharField(
        max_length=20,
        help_text="Unit of measurement (lbs, inches, min:sec, miles)"
    )

    # Timeline
    start_date = models.DateField(default=date.today)
    target_date = models.DateField(
        help_text="Target completion date"
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Link to general Goal if desired
    linked_goal = models.ForeignKey(
        'goals.Goal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fitness_goals',
        help_text="Optional link to a general goal"
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active', '-created_at']),
            models.Index(fields=['user', 'goal_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    @property
    def progress_percentage(self):
        """Calculate progress toward goal as a percentage (0-100)."""
        if self.current_value is None:
            return 0

        total_change = float(self.target_value) - float(self.start_value)
        if total_change == 0:
            return 100 if self.current_value == self.target_value else 0

        current_change = float(self.current_value) - float(self.start_value)
        progress = (current_change / total_change) * 100
        return min(100, max(0, progress))

    @property
    def days_remaining(self):
        """Calculate days remaining until target date."""
        if not self.target_date:
            return None
        delta = self.target_date - date.today()
        return max(0, delta.days)

    @property
    def days_elapsed(self):
        """Calculate days elapsed since start date."""
        if not self.start_date:
            return 0
        delta = date.today() - self.start_date
        return max(0, delta.days)

    @property
    def total_days(self):
        """Calculate total days in goal timeline."""
        if not self.start_date or not self.target_date:
            return None
        return (self.target_date - self.start_date).days

    @property
    def expected_value_today(self):
        """
        Linear progression: where should we be today?
        Returns the expected value based on linear progress from start to target.
        """
        if not self.start_date or not self.target_date:
            return None

        total_days = self.total_days
        if total_days is None or total_days <= 0:
            return float(self.target_value)

        days_elapsed = self.days_elapsed
        progress_ratio = min(1.0, days_elapsed / total_days)

        expected = float(self.start_value) + (float(self.target_value) - float(self.start_value)) * progress_ratio
        return round(expected, 2)

    @property
    def is_on_track(self):
        """
        Are we ahead or behind schedule?
        Returns True if on track, False if behind, None if cannot determine.
        """
        if self.current_value is None or self.expected_value_today is None:
            return None

        current = float(self.current_value)
        expected = self.expected_value_today

        # For goals where lower is better (weight loss, faster time)
        if float(self.target_value) < float(self.start_value):
            return current <= expected

        # For goals where higher is better (distance, muscle gain)
        return current >= expected

    @property
    def variance_from_schedule(self):
        """
        How far ahead/behind schedule are we?
        Positive = ahead of schedule, Negative = behind schedule.
        """
        if self.current_value is None or self.expected_value_today is None:
            return None

        current = float(self.current_value)
        expected = self.expected_value_today

        # For goals where lower is better, invert the sign
        if float(self.target_value) < float(self.start_value):
            return expected - current  # Positive if current is lower (better)
        return current - expected  # Positive if current is higher (better)

    @property
    def variance_display(self):
        """Format variance for display."""
        variance = self.variance_from_schedule
        if variance is None:
            return "N/A"

        sign = "+" if variance >= 0 else ""
        if self.goal_type == 'cardio_time':
            # Convert decimal minutes to MM:SS format
            abs_var = abs(variance)
            minutes = int(abs_var)
            seconds = int((abs_var - minutes) * 60)
            return f"{sign}{'-' if variance < 0 else ''}{minutes}:{seconds:02d}"
        else:
            return f"{sign}{variance:.1f} {self.unit}"

    @property
    def on_track_status(self):
        """Return status string: 'ahead', 'behind', 'on_track', or 'unknown'."""
        if self.is_on_track is None:
            return 'unknown'
        if self.is_on_track:
            variance = self.variance_from_schedule
            if variance and abs(variance) < 0.5:
                return 'on_track'
            return 'ahead'
        return 'behind'

    @property
    def icon(self):
        """Return Bootstrap icon based on goal type."""
        icons = {
            'weight': 'bi-speedometer',
            'measurement': 'bi-rulers',
            'cardio': 'bi-stopwatch',
            'cardio_time': 'bi-stopwatch',
            'cardio_distance': 'bi-signpost-2',
        }
        return icons.get(self.goal_type, 'bi-bullseye')

    @property
    def target_time_display(self):
        """Return formatted target time (MM:SS)."""
        if self.target_time_minutes is None:
            return None
        seconds = self.target_time_seconds or 0
        return f"{self.target_time_minutes}:{seconds:02d}"

    @property
    def is_cardio_combo(self):
        """Check if this is a combo cardio goal (distance + time)."""
        return self.goal_type == 'cardio' and self.target_distance and self.target_time_minutes

    def update_progress(self, new_value):
        """Update current value and check for completion."""
        self.current_value = new_value

        # Check if goal is achieved
        if float(self.target_value) < float(self.start_value):
            # Lower is better (weight loss, faster time)
            achieved = float(new_value) <= float(self.target_value)
        else:
            # Higher is better
            achieved = float(new_value) >= float(self.target_value)

        if achieved and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()

        self.save()


class FitnessGoalProgress(models.Model):
    """Track progress history for fitness goals."""

    goal = models.ForeignKey(
        FitnessGoal,
        on_delete=models.CASCADE,
        related_name='progress_entries'
    )
    value = models.DecimalField(
        max_digits=6,
        decimal_places=2
    )
    logged_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['goal', '-logged_at']),
        ]

    def __str__(self):
        return f"{self.goal.title} - {self.value} on {self.logged_at.date()}"
