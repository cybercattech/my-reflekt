from django import template
from datetime import datetime
from apps.analytics.services.mood import MOOD_EMOJIS

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def format_iso_date(iso_string, format_string='%b %d, %Y'):
    """Convert ISO date string to formatted date.

    Usage: {{ day.date|format_iso_date }} -> "Jan 15, 2024"
           {{ day.date|format_iso_date:"%B %d" }} -> "January 15"
    """
    if not iso_string:
        return ''
    try:
        dt = datetime.fromisoformat(str(iso_string))
        return dt.strftime(format_string)
    except (ValueError, TypeError):
        return iso_string


@register.filter
def mood_emoji(mood):
    """Convert mood to emoji."""
    return MOOD_EMOJIS.get(mood, '')


@register.filter
def clean_theme(theme):
    """Clean theme name by replacing underscores with spaces and title casing.

    Usage: {{ theme|clean_theme }} -> "Personal Growth" instead of "personal_growth"
    """
    if not theme:
        return ''
    return str(theme).replace('_', ' ').title()


@register.filter
def temperature(celsius, unit='C'):
    """
    Convert temperature from Celsius to the specified unit.

    Usage: {{ temp|temperature:'F' }} or {{ temp|temperature:user.profile.temperature_unit }}
    """
    if celsius is None:
        return ''

    try:
        celsius = float(celsius)
    except (TypeError, ValueError):
        return ''

    if unit == 'F':
        fahrenheit = (celsius * 9/5) + 32
        return f"{fahrenheit:.0f}°F"
    else:
        return f"{celsius:.0f}°C"
