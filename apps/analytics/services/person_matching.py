"""
Person matching service for social analytics.

Uses fuzzy string matching to identify the same person across
multiple /person captures, enabling social pattern analysis.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Threshold for fuzzy matching (0-100)
FUZZY_MATCH_THRESHOLD = 85


def normalize_name(name):
    """
    Normalize a person's name for comparison.

    - Lowercase
    - Strip titles (Mr, Mrs, Dr, etc.)
    - Collapse whitespace
    """
    if not name:
        return ''

    name = name.lower().strip()

    # Remove common titles
    titles = [
        r'^(mr|mrs|ms|miss|dr|prof|professor)\b\.?\s*',
        r'\b(jr|sr|ii|iii|iv)\b\.?$',
    ]
    for pattern in titles:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def find_matching_person(user, name):
    """
    Find an existing TrackedPerson with fuzzy matching.

    Args:
        user: The user to search people for
        name: Person name to match

    Returns:
        tuple: (TrackedPerson or None, confidence score 0-100)
    """
    from apps.analytics.models import TrackedPerson

    normalized = normalize_name(name)

    if not normalized:
        return None, 0

    # Try exact match first (fast path)
    exact = TrackedPerson.objects.filter(
        user=user,
        normalized_name=normalized
    ).first()

    if exact:
        return exact, 100

    # Fuzzy match
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("rapidfuzz not installed, falling back to exact match only")
        return None, 0

    candidates = TrackedPerson.objects.filter(user=user)
    best_match = None
    best_score = 0

    for person in candidates:
        score = fuzz.ratio(normalized, person.normalized_name)

        # Also check for partial matches (first name only, etc.)
        partial_score = fuzz.partial_ratio(normalized, person.normalized_name)

        # Use the higher of the two scores
        final_score = max(score, partial_score * 0.9)  # Slight penalty for partial

        if final_score > best_score:
            best_score = final_score
            best_match = person

    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match, best_score

    return None, best_score


def get_or_create_tracked_person(user, capture):
    """
    Get or create a TrackedPerson from an EntryCapture.

    Links the capture and updates mention stats.

    Args:
        user: The user who owns the capture
        capture: An EntryCapture with capture_type='person'

    Returns:
        TrackedPerson or None if capture has no name
    """
    from apps.analytics.models import TrackedPerson

    data = capture.data
    name = data.get('name', '').strip()

    if not name:
        logger.warning(f"Person capture {capture.id} has no name")
        return None

    # Find or create the person
    existing, confidence = find_matching_person(user, name)

    if existing:
        person = existing
        logger.info(f"Matched person capture to existing: {person.name} (confidence: {confidence}%)")
    else:
        # Create new person
        person = TrackedPerson.objects.create(
            user=user,
            name=name,
            normalized_name=normalize_name(name),
        )
        logger.info(f"Created new TrackedPerson: {person.name}")

    # Link this capture
    person.captures.add(capture)

    # Update stats
    person.mention_count = person.captures.count()

    entry_date = capture.entry.entry_date

    # Update date range
    if not person.first_mention_date or entry_date < person.first_mention_date:
        person.first_mention_date = entry_date
    if not person.last_mention_date or entry_date > person.last_mention_date:
        person.last_mention_date = entry_date

    person.save()
    return person
