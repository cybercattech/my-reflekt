"""
Wellness tracking models for pain, intimacy, and cycle tracking.
"""
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
