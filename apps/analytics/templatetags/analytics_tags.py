from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def mood_emoji(mood):
    """Convert mood to emoji."""
    emoji_map = {
        'ecstatic': '🤩',
        'happy': '😊',
        'neutral': '😐',
        'sad': '😢',
        'angry': '😠',
    }
    return emoji_map.get(mood, '')


@register.filter
def clean_theme(theme):
    """Clean up theme name for display (replace underscores, title case)."""
    if not theme:
        return ''
    return theme.replace('_', ' ').title()


@register.filter
def temperature(value, unit='C'):
    """
    Convert temperature to specified unit and format for display.
    Temperature is stored in Celsius, converts to Fahrenheit if unit is 'F'.
    """
    if value is None:
        return ''
    try:
        temp = float(value)
        if unit == 'F':
            temp = (temp * 9/5) + 32
        return f"{round(temp)}°{unit}"
    except (ValueError, TypeError):
        return ''
