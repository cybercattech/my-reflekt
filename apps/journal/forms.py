from django import forms
from .models import Entry


class EntryForm(forms.ModelForm):
    """Form for creating and editing journal entries."""

    class Meta:
        model = Entry
        fields = ['title', 'content', 'entry_date', 'mood', 'energy', 'city', 'country_code']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Title (optional)',
            }),
            'content': forms.Textarea(attrs={
                'id': 'editor',
                'class': 'w-full',
                'placeholder': 'Start writing...',
                'rows': 15,
            }),
            'entry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            }),
            'mood': forms.Select(attrs={
                'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            }),
            'energy': forms.Select(attrs={
                'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make mood and energy choices include empty option
        self.fields['mood'].choices = [('', '-- Select mood --')] + list(Entry.MOOD_CHOICES)
        self.fields['energy'].choices = [('', '-- Select energy --')] + list(Entry.ENERGY_CHOICES)
