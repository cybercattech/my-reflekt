"""
Forms for wellness tracking including body fitness, pain logs, and cycle tracking.
"""
from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator

from .models import (
    BodyMetric,
    CardioLog,
    FitnessGoal,
    FitnessGoalProgress,
    PainLog,
    CycleLog,
)


# =============================================================================
# Body Fitness Forms
# =============================================================================

class BodyMetricForm(forms.ModelForm):
    """Form for logging body metrics (weight and measurements)."""

    class Meta:
        model = BodyMetric
        fields = [
            'weight', 'weight_unit',
            'waist', 'chest', 'biceps', 'thighs', 'hips', 'body_fat',
            'measurement_unit', 'notes'
        ]
        widgets = {
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'weight_unit': forms.Select(attrs={
                'class': 'form-select'
            }),
            'waist': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'chest': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'biceps': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'thighs': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'hips': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0'
            }),
            'body_fat': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '0.0',
                'min': '0',
                'max': '100'
            }),
            'measurement_unit': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes...'
            }),
        }

    def clean_body_fat(self):
        body_fat = self.cleaned_data.get('body_fat')
        if body_fat is not None and (body_fat < 0 or body_fat > 100):
            raise forms.ValidationError("Body fat percentage must be between 0 and 100.")
        return body_fat


class QuickWeightForm(forms.Form):
    """Simplified form for quick weight logging."""
    weight = forms.DecimalField(
        max_digits=5,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'step': '0.1',
            'placeholder': 'Enter weight',
            'autofocus': True
        })
    )
    weight_unit = forms.ChoiceField(
        choices=BodyMetric.WEIGHT_UNIT_CHOICES,
        initial='lbs',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )


class CardioLogForm(forms.ModelForm):
    """Form for logging cardio activities."""

    class Meta:
        model = CardioLog
        fields = ['activity_type', 'distance', 'duration_minutes', 'duration_seconds', 'notes']
        widgets = {
            'activity_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'distance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00',
                'min': '0'
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'min',
                'min': '0'
            }),
            'duration_seconds': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'sec',
                'min': '0',
                'max': '59'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes...'
            }),
        }

    def clean_duration_seconds(self):
        seconds = self.cleaned_data.get('duration_seconds')
        if seconds is not None and (seconds < 0 or seconds > 59):
            raise forms.ValidationError("Seconds must be between 0 and 59.")
        return seconds


class FitnessGoalForm(forms.ModelForm):
    """Form for creating and editing fitness goals."""

    # Override to remove the empty "-------" option and hide legacy types
    GOAL_TYPE_CHOICES_FILTERED = [
        ('weight', 'Weight Goal'),
        ('measurement', 'Measurement Goal'),
        ('cardio', 'Cardio Goal'),
    ]

    goal_type = forms.ChoiceField(
        choices=GOAL_TYPE_CHOICES_FILTERED,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = FitnessGoal
        fields = [
            'title', 'goal_type', 'measurement_type', 'activity_type',
            'target_distance', 'target_time_minutes', 'target_time_seconds',
            'start_value', 'target_value', 'unit',
            'start_date', 'target_date', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Lose 20 lbs by Summer'
            }),
            'measurement_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'activity_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'target_distance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 3.0'
            }),
            'target_time_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'min',
                'min': '0'
            }),
            'target_time_seconds': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'sec',
                'min': '0',
                'max': '59'
            }),
            'start_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Current value'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Target value'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., lbs, inches, min'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'target_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes about this goal...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make some fields not required at form level (handled in clean)
        self.fields['measurement_type'].required = False
        self.fields['activity_type'].required = False
        self.fields['target_distance'].required = False
        self.fields['target_time_minutes'].required = False
        self.fields['target_time_seconds'].required = False

    def clean(self):
        cleaned_data = super().clean()
        goal_type = cleaned_data.get('goal_type')

        # Validate based on goal type
        if goal_type in ['weight', 'measurement']:
            if not cleaned_data.get('measurement_type'):
                self.add_error('measurement_type', 'Required for weight/measurement goals.')

        # New combined cardio goal type
        if goal_type == 'cardio':
            if not cleaned_data.get('activity_type'):
                self.add_error('activity_type', 'Required for cardio goals.')
            if not cleaned_data.get('target_distance'):
                self.add_error('target_distance', 'Required for cardio goals (e.g., 3 miles).')
            if not cleaned_data.get('target_time_minutes'):
                self.add_error('target_time_minutes', 'Required for cardio goals (target time).')
            # Validate seconds range
            seconds = cleaned_data.get('target_time_seconds')
            if seconds is not None and (seconds < 0 or seconds > 59):
                self.add_error('target_time_seconds', 'Seconds must be between 0 and 59.')

        # Legacy cardio types
        if goal_type in ['cardio_time', 'cardio_distance']:
            if not cleaned_data.get('activity_type'):
                self.add_error('activity_type', 'Required for cardio goals.')
        if goal_type == 'cardio_time':
            if not cleaned_data.get('target_distance'):
                self.add_error('target_distance', 'Required for cardio time goals (e.g., 3 miles).')

        # Validate dates
        start_date = cleaned_data.get('start_date')
        target_date = cleaned_data.get('target_date')
        if start_date and target_date and target_date <= start_date:
            self.add_error('target_date', 'Target date must be after start date.')

        return cleaned_data


class FitnessGoalProgressForm(forms.ModelForm):
    """Form for logging progress on a fitness goal."""

    class Meta:
        model = FitnessGoalProgress
        fields = ['value', 'notes']
        widgets = {
            'value': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'step': '0.01',
                'placeholder': 'Enter new value',
                'autofocus': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes...'
            }),
        }


# =============================================================================
# Pain Log Forms (existing functionality)
# =============================================================================

class PainLogForm(forms.ModelForm):
    """Form for logging pain episodes."""

    class Meta:
        model = PainLog
        fields = ['location', 'intensity', 'pain_type', 'duration', 'notes']
        widgets = {
            'location': forms.Select(attrs={
                'class': 'form-select'
            }),
            'intensity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '10',
                'placeholder': '1-10'
            }),
            'pain_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'duration': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional details...'
            }),
        }


class CycleLogForm(forms.ModelForm):
    """Form for logging cycle events."""

    class Meta:
        model = CycleLog
        fields = ['event_type', 'log_date', 'flow_level', 'notes']
        widgets = {
            'event_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'log_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'flow_level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes...'
            }),
        }
