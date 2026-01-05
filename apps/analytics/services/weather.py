"""
Weather data service using OpenWeatherMap API for current weather
and Open-Meteo API for historical weather.

Fetches current and historical weather conditions for a city.
"""
import logging
import requests
from typing import Dict, Optional
from datetime import date, datetime
from django.conf import settings


logger = logging.getLogger(__name__)

# OpenWeatherMap API base URLs
OWM_API_URL = 'https://api.openweathermap.org/data/2.5/weather'
OWM_GEOCODING_URL = 'https://api.openweathermap.org/geo/1.0/direct'

# Open-Meteo API base URL (free, no API key needed)
OPEN_METEO_URL = 'https://archive-api.open-meteo.com/v1/archive'

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


# ============================================================================
# HISTORICAL WEATHER (Open-Meteo API)
# ============================================================================

# WMO Weather Code mapping to conditions
# https://open-meteo.com/en/docs
WMO_WEATHER_CODES = {
    0: ('clear', 'Clear sky'),
    1: ('clear', 'Mainly clear'),
    2: ('clouds', 'Partly cloudy'),
    3: ('clouds', 'Overcast'),
    45: ('fog', 'Fog'),
    48: ('fog', 'Depositing rime fog'),
    51: ('drizzle', 'Light drizzle'),
    53: ('drizzle', 'Moderate drizzle'),
    55: ('drizzle', 'Dense drizzle'),
    61: ('rain', 'Slight rain'),
    63: ('rain', 'Moderate rain'),
    65: ('rain', 'Heavy rain'),
    71: ('snow', 'Slight snow fall'),
    73: ('snow', 'Moderate snow fall'),
    75: ('snow', 'Heavy snow fall'),
    77: ('snow', 'Snow grains'),
    80: ('rain', 'Slight rain showers'),
    81: ('rain', 'Moderate rain showers'),
    82: ('rain', 'Violent rain showers'),
    85: ('snow', 'Slight snow showers'),
    86: ('snow', 'Heavy snow showers'),
    95: ('thunderstorm', 'Thunderstorm'),
    96: ('thunderstorm', 'Thunderstorm with slight hail'),
    99: ('thunderstorm', 'Thunderstorm with heavy hail'),
}


def get_city_coordinates(city: str, country_code: str = 'US') -> Optional[Dict]:
    """
    Get latitude and longitude for a city using OpenWeatherMap Geocoding API.

    Args:
        city: City name
        country_code: Two-letter country code

    Returns:
        Dict with 'lat' and 'lon' or None if not found
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
            'limit': 1,
        }

        response = requests.get(OWM_GEOCODING_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return {
                    'lat': data[0]['lat'],
                    'lon': data[0]['lon'],
                    'name': data[0].get('name', city),
                }
            else:
                logger.warning(f"City not found: {location}")
                return None
        else:
            logger.error(f"Geocoding API error: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Geocoding API timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error geocoding: {e}")
        return None


def get_historical_weather(city: str, entry_date: date, country_code: str = 'US') -> Optional[Dict]:
    """
    Fetch historical weather data for a specific date using Open-Meteo API.

    Args:
        city: City name
        entry_date: Date to fetch weather for (date object or datetime)
        country_code: Two-letter country code

    Returns:
        Dict with weather data or None if unavailable
    """
    # Convert datetime to date if needed
    if isinstance(entry_date, datetime):
        entry_date = entry_date.date()

    # Get coordinates for the city
    coords = get_city_coordinates(city, country_code)
    if not coords:
        logger.warning(f"Could not get coordinates for {city}")
        return None

    try:
        # Format date as YYYY-MM-DD
        date_str = entry_date.strftime('%Y-%m-%d')

        params = {
            'latitude': coords['lat'],
            'longitude': coords['lon'],
            'start_date': date_str,
            'end_date': date_str,
            'daily': 'weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum',
            'timezone': 'auto',
        }

        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return parse_open_meteo_response(data, city, country_code)
        else:
            logger.error(f"Open-Meteo API error: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Open-Meteo API timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Open-Meteo API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching historical weather: {e}")
        return None


def parse_open_meteo_response(data: Dict, city: str, country_code: str) -> Dict:
    """
    Extract relevant weather data from Open-Meteo response.

    Args:
        data: Raw API response from Open-Meteo
        city: City name
        country_code: Country code

    Returns:
        Dict with parsed weather data in our standard format
    """
    try:
        daily = data.get('daily', {})

        # Get first (and only) day's data
        weather_code = daily.get('weathercode', [None])[0]
        temp_max = daily.get('temperature_2m_max', [None])[0]
        temp_min = daily.get('temperature_2m_min', [None])[0]
        precipitation = daily.get('precipitation_sum', [0])[0]

        # Calculate average temperature
        if temp_max is not None and temp_min is not None:
            temp_avg = (temp_max + temp_min) / 2
        else:
            temp_avg = None

        # Map WMO weather code to our condition
        condition = 'clear'
        description = 'Clear'
        if weather_code is not None and weather_code in WMO_WEATHER_CODES:
            condition, description = WMO_WEATHER_CODES[weather_code]

        return {
            'condition': condition,
            'description': description,
            'temperature': temp_avg,  # Average temperature in Celsius
            'temp_max': temp_max,
            'temp_min': temp_min,
            'precipitation': precipitation,
            'humidity': None,  # Not available in historical data
            'icon_code': '',
            'icon': get_weather_icon_class(condition, description),
            'display_name': get_weather_display_name(condition),
            'location': f"{city}, {country_code}",
        }

    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error parsing Open-Meteo response: {e}")
        return None
