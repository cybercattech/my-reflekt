"""
Moon phase calculation service.

Calculates moon phase based on date using the synodic month algorithm.
No external API needed - pure mathematical calculation.
"""
import math
from datetime import datetime, date
from typing import Tuple, Dict


# Moon phase names
MOON_PHASES = [
    'new_moon',
    'waxing_crescent',
    'first_quarter',
    'waxing_gibbous',
    'full_moon',
    'waning_gibbous',
    'last_quarter',
    'waning_crescent',
]

# Display names for UI
MOON_PHASE_DISPLAY = {
    'new_moon': 'New Moon',
    'waxing_crescent': 'Waxing Crescent',
    'first_quarter': 'First Quarter',
    'waxing_gibbous': 'Waxing Gibbous',
    'full_moon': 'Full Moon',
    'waning_gibbous': 'Waning Gibbous',
    'last_quarter': 'Last Quarter',
    'waning_crescent': 'Waning Crescent',
}

# Bootstrap icons for moon phases
MOON_PHASE_ICONS = {
    'new_moon': 'bi-moon',
    'waxing_crescent': 'bi-moon',
    'first_quarter': 'bi-circle-half',
    'waxing_gibbous': 'bi-circle-half',
    'full_moon': 'bi-circle-fill',
    'waning_gibbous': 'bi-circle-half',
    'last_quarter': 'bi-circle-half',
    'waning_crescent': 'bi-moon',
}

# Synodic month (average lunar cycle) in days
SYNODIC_MONTH = 29.53058867

# Known new moon reference date (January 6, 2000 at 18:14 UTC)
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, 0)


def calculate_moon_phase(target_date: date) -> Tuple[str, float]:
    """
    Calculate moon phase for a given date.

    Uses the synodic month algorithm based on a known new moon date.

    Args:
        target_date: The date to calculate moon phase for

    Returns:
        Tuple of (phase_name, illumination)
        - phase_name: one of MOON_PHASES
        - illumination: 0.0 to 1.0 (0 = new moon, 1 = full moon)
    """
    # Convert to datetime at noon for calculation
    if isinstance(target_date, date) and not isinstance(target_date, datetime):
        target_dt = datetime(target_date.year, target_date.month, target_date.day, 12, 0, 0)
    else:
        target_dt = target_date

    # Calculate days since known new moon
    diff = target_dt - KNOWN_NEW_MOON
    days_since = diff.total_seconds() / 86400.0

    # Calculate position in lunar cycle (0 to 1)
    lunar_cycle = (days_since % SYNODIC_MONTH) / SYNODIC_MONTH

    # Calculate illumination (simplified: 0 at new moon, 100 at full moon)
    # Uses cosine function for more accurate illumination curve
    illumination_decimal = (1 - math.cos(lunar_cycle * 2 * math.pi)) / 2
    illumination_percent = illumination_decimal * 100

    # Determine phase name based on lunar cycle position
    phase_name = get_moon_phase_name(lunar_cycle)

    return phase_name, round(illumination_percent, 1)


def get_moon_phase_name(lunar_cycle: float) -> str:
    """
    Convert lunar cycle position (0-1) to phase name.

    Args:
        lunar_cycle: Position in lunar cycle (0 = new moon, 0.5 = full moon)

    Returns:
        Phase name string
    """
    # 8 phases, each ~3.69 days / 12.5% of cycle
    phase_index = int(lunar_cycle * 8) % 8
    return MOON_PHASES[phase_index]


def get_moon_illumination(target_date: date) -> float:
    """
    Get just the illumination percentage for a date.

    Args:
        target_date: The date to calculate illumination for

    Returns:
        Illumination as float 0.0 to 1.0
    """
    _, illumination = calculate_moon_phase(target_date)
    return illumination


def get_phase_display_name(phase_name: str) -> str:
    """Get human-readable display name for a phase."""
    return MOON_PHASE_DISPLAY.get(phase_name, phase_name.replace('_', ' ').title())


def get_phase_icon(phase_name: str) -> str:
    """Get Bootstrap icon class for a phase."""
    return MOON_PHASE_ICONS.get(phase_name, 'bi-moon')


def get_moon_data(target_date: date) -> Dict:
    """
    Get complete moon data for a date.

    Args:
        target_date: The date to get moon data for

    Returns:
        Dict with phase, illumination, display_name, icon
    """
    phase_name, illumination_percent = calculate_moon_phase(target_date)

    return {
        'phase': phase_name,
        'illumination': illumination_percent,
        'illumination_percent': round(illumination_percent),
        'display_name': get_phase_display_name(phase_name),
        'icon': get_phase_icon(phase_name),
    }
