"""
Book matching service for tracking reading journeys.

Uses fuzzy string matching to identify the same book across
multiple /book captures, enabling progress tracking over time.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Threshold for fuzzy matching (0-100)
FUZZY_MATCH_THRESHOLD = 85


def normalize_text(text):
    """
    Normalize text for comparison.

    - Lowercase
    - Strip punctuation
    - Collapse whitespace
    """
    if not text:
        return ''
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def find_matching_book(user, title, author=None):
    """
    Find an existing TrackedBook with fuzzy matching.

    Args:
        user: The user to search books for
        title: Book title to match
        author: Optional author name

    Returns:
        tuple: (TrackedBook or None, confidence score 0-100)
    """
    from apps.analytics.models import TrackedBook

    normalized_title = normalize_text(title)
    normalized_author = normalize_text(author) if author else ''

    if not normalized_title:
        return None, 0

    # Try exact match first (fast path)
    exact_query = TrackedBook.objects.filter(
        user=user,
        normalized_title=normalized_title
    )
    if normalized_author:
        exact_query = exact_query.filter(normalized_author=normalized_author)

    if exact_query.exists():
        return exact_query.first(), 100

    # Fuzzy match against all user's books
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("rapidfuzz not installed, falling back to exact match only")
        return None, 0

    candidates = TrackedBook.objects.filter(user=user)
    best_match = None
    best_score = 0

    for book in candidates:
        # Title similarity is weighted most heavily
        title_score = fuzz.ratio(normalized_title, book.normalized_title)

        # If both have authors, factor that in
        if normalized_author and book.normalized_author:
            author_score = fuzz.ratio(normalized_author, book.normalized_author)
            # 70% title, 30% author
            score = (title_score * 0.7) + (author_score * 0.3)
        else:
            score = title_score

        if score > best_score:
            best_score = score
            best_match = book

    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match, best_score

    return None, best_score


def get_or_create_tracked_book(user, capture):
    """
    Get or create a TrackedBook from an EntryCapture.

    Links the capture to the book and updates status/progress.

    Args:
        user: The user who owns the capture
        capture: An EntryCapture with capture_type='book'

    Returns:
        TrackedBook or None if capture has no title
    """
    from apps.analytics.models import TrackedBook

    data = capture.data
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()

    if not title:
        logger.warning(f"Book capture {capture.id} has no title")
        return None

    # Find or create the book
    existing_book, confidence = find_matching_book(user, title, author)

    if existing_book:
        book = existing_book
        logger.info(f"Matched book capture to existing: {book.title} (confidence: {confidence}%)")
    else:
        # Create new book
        book = TrackedBook.objects.create(
            user=user,
            title=title,
            normalized_title=normalize_text(title),
            author=author,
            normalized_author=normalize_text(author),
        )
        logger.info(f"Created new TrackedBook: {book.title}")

    # Link this capture to the book
    book.captures.add(capture)

    # Update book from capture data
    status = data.get('status', '').lower()
    entry_date = capture.entry.entry_date

    # Handle status transitions
    if status == 'finished':
        book.status = 'finished'
        # Only update finished_date if not already set or this is later
        if not book.finished_date or entry_date > book.finished_date:
            book.finished_date = entry_date
        # Update rating if provided
        if data.get('rating'):
            book.rating = int(data['rating'])
    elif status in ['started', 'reading']:
        # Only change to reading if not already finished
        if book.status != 'finished':
            book.status = 'reading'
        # Set started_date if not set
        if not book.started_date:
            book.started_date = entry_date
    elif status == 'abandoned':
        book.status = 'abandoned'
    elif status == 'want_to_read':
        if book.status not in ['reading', 'finished']:
            book.status = 'want_to_read'

    # Update page progress
    page = data.get('page')
    if page:
        try:
            page_num = int(page)
            if page_num > book.current_page:
                book.current_page = page_num
        except (ValueError, TypeError):
            pass

    # Update total pages if provided and not set
    total_pages = data.get('total_pages')
    if total_pages and not book.total_pages:
        try:
            book.total_pages = int(total_pages)
        except (ValueError, TypeError):
            pass

    book.save()
    return book
