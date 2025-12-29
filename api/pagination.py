"""
Custom pagination classes for the Reflekt API.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination


class StandardResultsPagination(PageNumberPagination):
    """
    Standard pagination with configurable page size.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LargeResultsPagination(PageNumberPagination):
    """
    Larger pagination for bulk data retrieval.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class JournalEntryCursorPagination(CursorPagination):
    """
    Cursor-based pagination for journal entries.
    More efficient for large datasets and infinite scrolling.
    """
    page_size = 20
    ordering = '-entry_date'
    cursor_query_param = 'cursor'
