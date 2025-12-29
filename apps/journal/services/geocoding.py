"""
Geocoding service using Nominatim (OpenStreetMap).

Provides location name to coordinates conversion with caching.
"""

import time
import urllib.request
import urllib.parse
import json
from django.utils import timezone


# Rate limiting - Nominatim requires max 1 request per second
_last_request_time = 0


def geocode_location(location_name):
    """
    Geocode a location name to lat/lng coordinates.

    Uses cached results when available, otherwise calls Nominatim API.
    Returns (lat, lng) tuple or (None, None) if geocoding fails.
    """
    from apps.journal.models import GeocodedLocation

    if not location_name or not location_name.strip():
        return None, None

    normalized_name = location_name.strip()

    # Check cache first
    try:
        cached = GeocodedLocation.objects.get(name__iexact=normalized_name)
        return cached.lat, cached.lng
    except GeocodedLocation.DoesNotExist:
        pass

    # Rate limiting - ensure at least 1 second between requests
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    # Call Nominatim API
    try:
        encoded_name = urllib.parse.quote(normalized_name)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded_name}&format=json&limit=1"

        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'Reflekt Journal App/1.0'}
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            _last_request_time = time.time()
            data = json.loads(response.read().decode('utf-8'))

            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lng = float(data[0]['lon'])

                # Cache the result
                GeocodedLocation.objects.update_or_create(
                    name__iexact=normalized_name,
                    defaults={
                        'name': normalized_name,
                        'lat': lat,
                        'lng': lng,
                    }
                )
                return lat, lng
            else:
                # Cache the failed lookup to avoid repeated API calls
                GeocodedLocation.objects.update_or_create(
                    name__iexact=normalized_name,
                    defaults={
                        'name': normalized_name,
                        'lat': None,
                        'lng': None,
                    }
                )
                return None, None

    except Exception:
        # On error, don't cache - allow retry later
        return None, None


def geocode_locations_batch(location_names):
    """
    Geocode multiple location names.

    Returns a dict mapping location name to (lat, lng) tuple.
    Respects rate limiting for uncached locations.
    """
    results = {}
    for name in location_names:
        if name:
            lat, lng = geocode_location(name)
            if lat is not None and lng is not None:
                results[name] = {'lat': lat, 'lng': lng}
    return results


def get_map_locations_for_user(user):
    """
    Get all geocoded locations for a user's travel captures only.

    Returns a list of dicts with location info for map markers:
    [
        {
            'name': 'Paris, France',
            'lat': 48.8566,
            'lng': 2.3522,
            'type': 'travel',
            'count': 3
        },
        ...
    ]
    """
    from apps.journal.models import EntryCapture
    from collections import Counter

    # Collect travel destinations only
    travel_destinations = Counter()

    captures = EntryCapture.objects.filter(
        entry__user=user,
        capture_type='travel'
    ).select_related('entry')

    for capture in captures:
        data = capture.data or {}
        dest = data.get('destination', '').strip()
        if dest:
            travel_destinations[dest] += 1

    # Geocode all unique locations
    geocoded = geocode_locations_batch(list(travel_destinations.keys()))

    # Build result list with coordinates
    results = []

    for dest, count in travel_destinations.items():
        if dest in geocoded:
            results.append({
                'name': dest,
                'lat': geocoded[dest]['lat'],
                'lng': geocoded[dest]['lng'],
                'type': 'travel',
                'count': count
            })

    return results
