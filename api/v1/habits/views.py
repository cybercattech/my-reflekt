"""
Habits views for the Reflekt API.
"""
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.habits.models import Habit, HabitCheckin
from api.permissions import IsOwner
from api.pagination import StandardResultsPagination

from .serializers import (
    HabitListSerializer, HabitDetailSerializer,
    HabitCreateSerializer, HabitUpdateSerializer,
    HabitCheckinSerializer, HabitCheckinCreateSerializer
)


class HabitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for habits.

    Provides CRUD operations for habits.
    Premium feature - requires premium subscription.
    """
    permission_classes = [IsAuthenticated, IsOwner]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """Return habits for the current user only."""
        return Habit.objects.filter(user=self.request.user).prefetch_related('checkins')

    def get_serializer_class(self):
        if self.action == 'list':
            return HabitListSerializer
        if self.action == 'create':
            return HabitCreateSerializer
        if self.action in ['update', 'partial_update']:
            return HabitUpdateSerializer
        return HabitDetailSerializer

    @extend_schema(
        summary="List habits",
        description="Get paginated list of habits for the current user.",
        parameters=[
            OpenApiParameter(name='category', description='Filter by category', required=False),
            OpenApiParameter(name='is_active', description='Filter by active status', required=False),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Apply filters
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        self.queryset = queryset
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a habit")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get a habit")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a habit")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partially update a habit")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete a habit")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(summary="Check in for a habit")
    @action(detail=True, methods=['post'])
    def checkin(self, request, pk=None):
        """Record a check-in for a habit."""
        habit = self.get_object()
        serializer = HabitCheckinCreateSerializer(
            data=request.data,
            context={'request': request, 'habit': habit}
        )
        serializer.is_valid(raise_exception=True)
        checkin = serializer.save()

        return Response(
            HabitCheckinSerializer(checkin).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(summary="Get today's habits")
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get habits due today with their completion status."""
        today = timezone.now().date()
        habits = self.get_queryset().filter(is_active=True)

        result = []
        for habit in habits:
            if habit.is_due_on_date(today):
                result.append({
                    'id': habit.id,
                    'name': habit.name,
                    'icon': habit.icon,
                    'color': habit.color,
                    'category': habit.category,
                    'is_completed': habit.is_completed_on_date(today),
                    'current_streak': habit.current_streak,
                })

        return Response(result)

    @extend_schema(summary="Get habit history")
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get check-in history for a habit."""
        habit = self.get_object()
        days = int(request.query_params.get('days', 30))

        checkins = habit.checkins.all()[:days]
        return Response(HabitCheckinSerializer(checkins, many=True).data)

    @extend_schema(summary="Get habit statistics")
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get habit statistics for the current user."""
        habits = self.get_queryset()
        active_habits = habits.filter(is_active=True)
        today = timezone.now().date()

        # Count habits due today
        due_today = sum(1 for h in active_habits if h.is_due_on_date(today))
        completed_today = sum(1 for h in active_habits if h.is_completed_on_date(today))

        # Calculate overall completion rate
        total_rate = sum(h.get_completion_rate(30) for h in active_habits)
        avg_rate = total_rate / active_habits.count() if active_habits.count() > 0 else 0

        stats = {
            'total': habits.count(),
            'active': active_habits.count(),
            'due_today': due_today,
            'completed_today': completed_today,
            'avg_completion_rate': round(avg_rate, 1),
            'total_completions': sum(h.total_completions for h in habits),
            'longest_streak': max((h.longest_streak for h in habits), default=0),
            'by_category': {},
        }

        for category, _ in Habit.CATEGORY_CHOICES:
            stats['by_category'][category] = habits.filter(category=category).count()

        return Response(stats)

    @extend_schema(summary="Get calendar data for a habit")
    @action(detail=True, methods=['get'])
    def calendar(self, request, pk=None):
        """Get calendar data for habit visualization."""
        habit = self.get_object()
        days = int(request.query_params.get('days', 90))
        today = timezone.now().date()

        calendar_data = []
        for i in range(days):
            date = today - timedelta(days=i)
            if date >= habit.start_date:
                is_due = habit.is_due_on_date(date)
                is_completed = habit.is_completed_on_date(date)
                calendar_data.append({
                    'date': date.isoformat(),
                    'is_due': is_due,
                    'is_completed': is_completed,
                    'status': 'completed' if is_completed else ('missed' if is_due else 'not_due')
                })

        return Response(calendar_data)
