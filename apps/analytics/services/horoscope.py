"""
Zodiac sign calculation service.

Calculates zodiac sign from birthday. No external API needed.
"""
from datetime import date
from typing import Dict, Optional, Tuple


# Zodiac signs with their date ranges (month, day)
# Each tuple: (sign_name, start_month, start_day, end_month, end_day)
ZODIAC_SIGNS = [
    ('capricorn', 12, 22, 1, 19),
    ('aquarius', 1, 20, 2, 18),
    ('pisces', 2, 19, 3, 20),
    ('aries', 3, 21, 4, 19),
    ('taurus', 4, 20, 5, 20),
    ('gemini', 5, 21, 6, 20),
    ('cancer', 6, 21, 7, 22),
    ('leo', 7, 23, 8, 22),
    ('virgo', 8, 23, 9, 22),
    ('libra', 9, 23, 10, 22),
    ('scorpio', 10, 23, 11, 21),
    ('sagittarius', 11, 22, 12, 21),
]

# Display names
ZODIAC_DISPLAY = {
    'aries': 'Aries',
    'taurus': 'Taurus',
    'gemini': 'Gemini',
    'cancer': 'Cancer',
    'leo': 'Leo',
    'virgo': 'Virgo',
    'libra': 'Libra',
    'scorpio': 'Scorpio',
    'sagittarius': 'Sagittarius',
    'capricorn': 'Capricorn',
    'aquarius': 'Aquarius',
    'pisces': 'Pisces',
}

# Zodiac symbols/emojis
ZODIAC_SYMBOLS = {
    'aries': '\u2648',  # ♈
    'taurus': '\u2649',  # ♉
    'gemini': '\u264a',  # ♊
    'cancer': '\u264b',  # ♋
    'leo': '\u264c',  # ♌
    'virgo': '\u264d',  # ♍
    'libra': '\u264e',  # ♎
    'scorpio': '\u264f',  # ♏
    'sagittarius': '\u2650',  # ♐
    'capricorn': '\u2651',  # ♑
    'aquarius': '\u2652',  # ♒
    'pisces': '\u2653',  # ♓
}

# Element associations
ZODIAC_ELEMENTS = {
    'aries': 'fire',
    'leo': 'fire',
    'sagittarius': 'fire',
    'taurus': 'earth',
    'virgo': 'earth',
    'capricorn': 'earth',
    'gemini': 'air',
    'libra': 'air',
    'aquarius': 'air',
    'cancer': 'water',
    'scorpio': 'water',
    'pisces': 'water',
}

# Element colors for UI
ELEMENT_COLORS = {
    'fire': '#ef4444',  # red
    'earth': '#84cc16',  # green
    'air': '#38bdf8',  # light blue
    'water': '#3b82f6',  # blue
}

# Date ranges for display
ZODIAC_DATE_RANGES = {
    'aries': 'Mar 21 - Apr 19',
    'taurus': 'Apr 20 - May 20',
    'gemini': 'May 21 - Jun 20',
    'cancer': 'Jun 21 - Jul 22',
    'leo': 'Jul 23 - Aug 22',
    'virgo': 'Aug 23 - Sep 22',
    'libra': 'Sep 23 - Oct 22',
    'scorpio': 'Oct 23 - Nov 21',
    'sagittarius': 'Nov 22 - Dec 21',
    'capricorn': 'Dec 22 - Jan 19',
    'aquarius': 'Jan 20 - Feb 18',
    'pisces': 'Feb 19 - Mar 20',
}


def get_zodiac_sign(birthday: date) -> Optional[str]:
    """
    Calculate zodiac sign from birthday.

    Args:
        birthday: Date of birth

    Returns:
        Zodiac sign name (lowercase) or None if invalid
    """
    if not birthday:
        return None

    month = birthday.month
    day = birthday.day

    for sign, start_m, start_d, end_m, end_d in ZODIAC_SIGNS:
        # Handle Capricorn which spans year boundary
        if start_m > end_m:  # Dec-Jan
            if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
                return sign
        else:
            if (month == start_m and day >= start_d) or \
               (month == end_m and day <= end_d) or \
               (start_m < month < end_m):
                return sign

    return None


def get_zodiac_display_name(sign: str) -> str:
    """Get human-readable display name for a sign."""
    return ZODIAC_DISPLAY.get(sign, sign.title())


def get_zodiac_symbol(sign: str) -> str:
    """Get Unicode symbol for a sign."""
    return ZODIAC_SYMBOLS.get(sign, '')


def get_zodiac_element(sign: str) -> str:
    """Get element (fire, earth, air, water) for a sign."""
    return ZODIAC_ELEMENTS.get(sign, '')


def get_element_color(element: str) -> str:
    """Get color hex code for an element."""
    return ELEMENT_COLORS.get(element, '#6b7280')


def get_zodiac_date_range(sign: str) -> str:
    """Get date range string for a sign."""
    return ZODIAC_DATE_RANGES.get(sign, '')


def get_zodiac_data(birthday: date) -> Optional[Dict]:
    """
    Get complete zodiac data for a birthday.

    Args:
        birthday: Date of birth

    Returns:
        Dict with sign, display_name, symbol, element, color, date_range
        or None if birthday is None
    """
    sign = get_zodiac_sign(birthday)
    if not sign:
        return None

    element = get_zodiac_element(sign)

    return {
        'sign': sign,
        'display_name': get_zodiac_display_name(sign),
        'symbol': get_zodiac_symbol(sign),
        'element': element,
        'element_color': get_element_color(element),
        'date_range': get_zodiac_date_range(sign),
    }


def get_signs_by_element(element: str) -> list:
    """Get all signs for a given element."""
    return [sign for sign, elem in ZODIAC_ELEMENTS.items() if elem == element]
