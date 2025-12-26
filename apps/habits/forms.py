from django import forms
from .models import Habit


WEEKDAY_CHOICES = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class HabitForm(forms.ModelForm):
    """Form for creating and editing habits."""

    specific_days_choices = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Which days?"
    )

    class Meta:
        model = Habit
        fields = [
            'name', 'description', 'icon', 'color', 'category',
            'frequency_type', 'times_per_week', 'start_date', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Morning meditation'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional description...'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'bi-heart'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'frequency_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'frequencyType'
            }),
            'times_per_week': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '7'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-populate specific_days_choices from model
        if self.instance.pk and self.instance.specific_days:
            self.initial['specific_days_choices'] = self.instance.specific_days.split(',')

    def clean(self):
        cleaned_data = super().clean()
        frequency_type = cleaned_data.get('frequency_type')
        times_per_week = cleaned_data.get('times_per_week')
        specific_days = self.data.getlist('specific_days_choices')

        if frequency_type == 'x_per_week' and (not times_per_week or times_per_week < 1):
            self.add_error('times_per_week', 'Please specify how many times per week.')

        if frequency_type == 'specific_days' and not specific_days:
            self.add_error('specific_days_choices', 'Please select at least one day.')

        # Store specific_days as comma-separated string
        if specific_days:
            cleaned_data['specific_days'] = ','.join(specific_days)
        else:
            cleaned_data['specific_days'] = ''

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.specific_days = self.cleaned_data.get('specific_days', '')
        if commit:
            instance.save()
        return instance
