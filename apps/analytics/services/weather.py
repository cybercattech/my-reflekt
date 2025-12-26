"""
Weather data service using OpenWeatherMap API.

Fetches current weather conditions for a city.
"""
import logging
import requests
from typing import Dict, Optional
from django.conf import settings


logger = logging.getLogger(__name__)

# OpenWeatherMap API base URL
OWM_API_URL = 'https://api.openweathermap.org/data/2.5/weather'

# Weather condition to Bootstrap icon mapping
WEATHER_ICONS = {
    'clear': 'bi-sun',
    'clouds': 'bi-cloud',
    'few clouds': 'bi-cloud-sun',
    'scattered clouds': 'bi-clouds',
    'broken clouds': 'bi-clouds',
    'overcast clouds': 'bi-clouds',
    'rain': 'bi-cloud-rain',
    'light rain': 'bi-cloud-drizzle',
    'moderate rain': 'bi-cloud-rain',
    'heavy rain': 'bi-cloud-rain-heavy',
    'drizzle': 'bi-cloud-drizzle',
    'thunderstorm': 'bi-cloud-lightning-rain',
    'snow': 'bi-cloud-snow',
    'light snow': 'bi-cloud-snow',
    'heavy snow': 'bi-snow',
    'mist': 'bi-cloud-haze',
    'fog': 'bi-cloud-fog',
    'haze': 'bi-cloud-haze',
    'smoke': 'bi-cloud-haze',
    'dust': 'bi-wind',
    'sand': 'bi-wind',
    'tornado': 'bi-tornado',
}

# Weather condition display names
WEATHER_DISPLAY = {
    'clear': 'Clear',
    'clouds': 'Cloudy',
    'rain': 'Rainy',
    'drizzle': 'Drizzle',
    'thunderstorm': 'Thunderstorm',
    'snow': 'Snow',
    'mist': 'Misty',
    'fog': 'Foggy',
    'haze': 'Hazy',
}


def get_weather_for_city(city: str, country_code: str = 'US') -> Optional[Dict]:
    """
    Fetch current weather from OpenWeatherMap.

    Args:
        city: City name
        country_code: Two-letter country code (default 'US')

    Returns:
        Dict with weather data or None if API call fails
    """
    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', '')

    if not api_key:
        logger.warning("OpenWeatherMap API key not configured")
        return None

    if not city:
        return None

    try:
        # Build query with city and country
        location = f"{city},{country_code}" if country_code else city

        params = {
            'q': location,
            'appid': api_key,
            'units': 'metric',  # Celsius
        }

        response = requests.get(OWM_API_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return parse_weather_response(data)
        elif response.status_code == 404:
            logger.warning(f"City not found: {location}")
            return None
        else:
            logger.error(f"OpenWeatherMap API error: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.error("OpenWeatherMap API timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenWeatherMap API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching weather: {e}")
        return None


def parse_weather_response(data: Dict) -> Dict:
    """
    Extract relevant weather data from OpenWeatherMap response.

    Args:
        data: Raw API response

    Returns:
        Dict with parsed weather data
    """
    weather = data.get('weather', [{}])[0]
    main = data.get('main', {})

    condition = weather.get('main', '').lower()
    description = weather.get('description', '')
    icon_code = weather.get('icon', '')

    return {
        'condition': condition,
        'description': description,
        'temperature': main.get('temp'),
        'feels_like': main.get('feels_like'),
        'humidity': main.get('humidity'),
        'icon_code': icon_code,
        'icon': get_weather_icon_class(condition, description),
        'display_name': get_weather_display_name(condition),
    }


def get_weather_icon_class(condition: str, description: str = '') -> str:
    """
    Map weather condition to Bootstrap icon class.

    Args:
        condition: Main weather condition (e.g., 'rain')
        description: Detailed description (e.g., 'light rain')

    Returns:
        Bootstrap icon class
    """
    # Try exact match on description first
    description_lower = description.lower()
    if description_lower in WEATHER_ICONS:
        return WEATHER_ICONS[description_lower]

    # Fall back to condition
    condition_lower = condition.lower()
    if condition_lower in WEATHER_ICONS:
        return WEATHER_ICONS[condition_lower]

    # Default
    return 'bi-cloud'


def get_weather_display_name(condition: str) -> str:
    """Get human-readable display name for a condition."""
    return WEATHER_DISPLAY.get(condition.lower(), condition.title())


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9/5) + 32


def format_temperature(celsius: float, unit: str = 'C') -> str:
    """
    Format temperature for display.

    Args:
        celsius: Temperature in Celsius
        unit: 'C' for Celsius, 'F' for Fahrenheit

    Returns:
        Formatted temperature string
    """
    if celsius is None:
        return ''

    if unit.upper() == 'F':
        temp = celsius_to_fahrenheit(celsius)
        return f"{temp:.0f}°F"
    else:
        return f"{celsius:.0f}°C"


def get_weather_data(city: str, country_code: str = 'US') -> Optional[Dict]:
    """
    Get complete weather data for a city.

    This is the main entry point for the weather service.

    Args:
        city: City name
        country_code: Two-letter country code

    Returns:
        Dict with weather data or None if unavailable
    """
    return get_weather_for_city(city, country_code)
