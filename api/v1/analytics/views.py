"""
Analytics views for the Reflekt API.
"""
from collections import Counter
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from rest_framework import generics, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.analytics.models import (
    EntryAnalysis, MonthlySnapshot, YearlyReview,
    TrackedBook, TrackedPerson, CaptureSnapshot
)
from apps.journal.models import Entry, EntryCapture
from api.pagination import StandardResultsPagination

from .serializers import (
    EntryAnalysisSerializer, MonthlySnapshotSerializer,
    YearlyReviewSerializer, TrackedBookSerializer,
    TrackedPersonSerializer, CaptureSnapshotSerializer,
    EntryCaptureListSerializer, DashboardStatsSerializer
)


class DashboardView(APIView):
    """
    Get dashboard overview statistics.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get dashboard statistics",
        description="Returns overview statistics for the current user's journal.",
        responses={200: DashboardStatsSerializer}
    )
    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        now = timezone.now()

        # Get entries
        entries = Entry.objects.filter(user=user)
        analyzed_entries = entries.filter(is_analyzed=True)

        # Calculate mood distribution
        mood_counts = dict(entries.values('mood').annotate(count=Count('mood')).values_list('mood', 'count'))

        # Calculate top themes from analyses
        themes = []
        for analysis in EntryAnalysis.objects.filter(entry__user=user).values_list('themes', flat=True):
            if analysis:
                themes.extend(analysis)
        theme_counts = Counter(themes).most_common(10)
        top_themes = [{'theme': t[0], 'count': t[1]} for t in theme_counts]

        # Get average sentiment
        avg_sentiment = EntryAnalysis.objects.filter(
            entry__user=user
        ).aggregate(avg=Avg('sentiment_score'))['avg'] or 0.0

        stats = {
            'total_entries': entries.count(),
            'total_words': entries.aggregate(total=Sum('word_count'))['total'] or 0,
            'avg_sentiment': round(avg_sentiment, 2),
            'current_streak': profile.current_streak if profile else 0,
            'longest_streak': profile.longest_streak if profile else 0,
            'mood_distribution': mood_counts,
            'entries_this_month': entries.filter(
                entry_date__year=now.year,
                entry_date__month=now.month
            ).count(),
            'entries_this_year': entries.filter(entry_date__year=now.year).count(),
            'top_themes': top_themes,
        }

        return Response(stats)


class MonthlySnapshotView(generics.RetrieveAPIView):
    """
    Get monthly snapshot for a specific month.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MonthlySnapshotSerializer

    @extend_schema(
        summary="Get monthly snapshot",
        parameters=[
            OpenApiParameter(name='year', description='Year (YYYY)', required=True),
            OpenApiParameter(name='month', description='Month (1-12)', required=True),
        ]
    )
    def get(self, request, year, month):
        snapshot = MonthlySnapshot.objects.filter(
            user=request.user,
            year=year,
            month=month
        ).first()

        if not snapshot:
            return Response(
                {'error': 'No data for this month.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(snapshot)
        return Response(serializer.data)


class MonthlySnapshotListView(generics.ListAPIView):
    """
    List all monthly snapshots for the user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MonthlySnapshotSerializer
    pagination_class = StandardResultsPagination

    @extend_schema(summary="List monthly snapshots")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return MonthlySnapshot.objects.filter(user=self.request.user)


class YearlyReviewView(generics.RetrieveAPIView):
    """
    Get yearly review for a specific year.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = YearlyReviewSerializer

    @extend_schema(
        summary="Get yearly review",
        parameters=[
            OpenApiParameter(name='year', description='Year (YYYY)', required=True),
        ]
    )
    def get(self, request, year):
        review = YearlyReview.objects.filter(
            user=request.user,
            year=year
        ).first()

        if not review:
            return Response(
                {'error': 'No yearly review for this year.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(review)
        return Response(serializer.data)


class CapturesListView(generics.ListAPIView):
    """
    List captures filtered by type.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EntryCaptureListSerializer
    pagination_class = StandardResultsPagination

    @extend_schema(
        summary="List captures",
        parameters=[
            OpenApiParameter(
                name='type',
                description='Capture type (book, watched, travel, workout, person, place, meal, dream, gratitude)',
                required=False
            ),
            OpenApiParameter(name='year', description='Filter by year', required=False),
            OpenApiParameter(name='month', description='Filter by month', required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = EntryCapture.objects.filter(
            entry__user=self.request.user
        ).select_related('entry').order_by('-entry__entry_date')

        capture_type = self.request.query_params.get('type')
        if capture_type:
            queryset = queryset.filter(capture_type=capture_type)

        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(entry__entry_date__year=year)

        month = self.request.query_params.get('month')
        if month:
            queryset = queryset.filter(entry__entry_date__month=month)

        return queryset


class TrackedBookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tracked books.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TrackedBookSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return TrackedBook.objects.filter(user=self.request.user)

    @extend_schema(
        summary="List tracked books",
        parameters=[
            OpenApiParameter(name='status', description='Filter by status', required=False),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        self.queryset = queryset
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Get reading stats")
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get book reading statistics."""
        books = self.get_queryset()

        stats = {
            'total': books.count(),
            'by_status': {
                'want_to_read': books.filter(status='want_to_read').count(),
                'reading': books.filter(status='reading').count(),
                'finished': books.filter(status='finished').count(),
                'abandoned': books.filter(status='abandoned').count(),
            },
            'finished_this_year': books.filter(
                status='finished',
                finished_date__year=timezone.now().year
            ).count(),
            'avg_rating': books.filter(rating__isnull=False).aggregate(
                avg=Avg('rating')
            )['avg'] or 0,
        }

        return Response(stats)


class TrackedPersonViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tracked people.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TrackedPersonSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return TrackedPerson.objects.filter(user=self.request.user)

    @extend_schema(
        summary="List tracked people",
        parameters=[
            OpenApiParameter(name='relationship', description='Filter by relationship', required=False),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        relationship = request.query_params.get('relationship')
        if relationship:
            queryset = queryset.filter(relationship=relationship)

        self.queryset = queryset
        return super().list(request, *args, **kwargs)


class SentimentTrendView(APIView):
    """
    Get sentiment trend data for charts.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get sentiment trend",
        parameters=[
            OpenApiParameter(name='days', description='Number of days (default 30)', required=False),
        ]
    )
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=days)

        analyses = EntryAnalysis.objects.filter(
            entry__user=request.user,
            entry__entry_date__gte=start_date,
            entry__entry_date__lte=end_date
        ).select_related('entry').order_by('entry__entry_date')

        data = [
            {
                'date': a.entry.entry_date.isoformat(),
                'sentiment': a.sentiment_score,
                'mood': a.detected_mood
            }
            for a in analyses
        ]

        return Response(data)


class MoodDistributionView(APIView):
    """
    Get mood distribution for charts.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get mood distribution",
        parameters=[
            OpenApiParameter(name='year', description='Filter by year', required=False),
            OpenApiParameter(name='month', description='Filter by month', required=False),
        ]
    )
    def get(self, request):
        entries = Entry.objects.filter(user=request.user)

        year = request.query_params.get('year')
        if year:
            entries = entries.filter(entry_date__year=year)

        month = request.query_params.get('month')
        if month:
            entries = entries.filter(entry_date__month=month)

        distribution = dict(
            entries.exclude(mood='').values('mood').annotate(
                count=Count('mood')
            ).values_list('mood', 'count')
        )

        return Response(distribution)
