from django import forms
from .models import Goal, Milestone


class GoalForm(forms.ModelForm):
    """Form for creating and editing SMART goals."""

    class Meta:
        model = Goal
        fields = [
            'title', 'description',
            'success_criteria', 'target_value', 'unit',
            'why_achievable', 'relevance',
            'start_date', 'due_date',
            'category', 'priority', 'status'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'What do you want to achieve?'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your goal in detail...'
            }),
            'success_criteria': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'How will you know when this goal is achieved?'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10',
                'step': '0.01'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., books, miles, pounds'
            }),
            'why_achievable': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Why is this goal achievable for you?'
            }),
            'relevance': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Why is this goal important to you?'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make SMART fields optional for flexibility
        for field in ['success_criteria', 'why_achievable', 'relevance']:
            self.fields[field].required = False


class MilestoneForm(forms.ModelForm):
    """Form for creating and editing milestones."""

    class Meta:
        model = Milestone
        fields = ['title', 'description', 'due_date', 'order']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Milestone title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional description...'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['due_date'].required = False
        self.fields['order'].required = False


class ProgressLogForm(forms.Form):
    """Simple form for logging progress updates."""
    value = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'New value',
            'step': '0.01'
        })
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional note about this update...'
        })
    )
