"""
Goals views for the Reflekt API.
"""
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.goals.models import Goal, Milestone, GoalProgressLog
from api.permissions import IsOwner, IsPremiumUser
from api.pagination import StandardResultsPagination

from .serializers import (
    GoalListSerializer, GoalDetailSerializer,
    GoalCreateSerializer, GoalUpdateSerializer,
    MilestoneSerializer, MilestoneCreateSerializer,
    GoalProgressLogSerializer, ProgressLogCreateSerializer
)


class GoalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for goals.

    Provides CRUD operations for goals.
    Premium feature - requires premium subscription.
    """
    permission_classes = [IsAuthenticated, IsOwner]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """Return goals for the current user only."""
        return Goal.objects.filter(user=self.request.user).prefetch_related(
            'milestones', 'progress_logs'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return GoalListSerializer
        if self.action == 'create':
            return GoalCreateSerializer
        if self.action in ['update', 'partial_update']:
            return GoalUpdateSerializer
        return GoalDetailSerializer

    @extend_schema(
        summary="List goals",
        description="Get paginated list of goals for the current user.",
        parameters=[
            OpenApiParameter(name='status', description='Filter by status', required=False),
            OpenApiParameter(name='category', description='Filter by category', required=False),
            OpenApiParameter(name='priority', description='Filter by priority', required=False),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        priority = request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        self.queryset = queryset
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a goal")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get a goal")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a goal")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partially update a goal")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete a goal")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(summary="Add a milestone to a goal")
    @action(detail=True, methods=['post'])
    def add_milestone(self, request, pk=None):
        """Add a milestone to a goal."""
        goal = self.get_object()
        serializer = MilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set order to next available
        max_order = goal.milestones.aggregate(
            models.Max('order')
        )['order__max'] or -1
        serializer.validated_data['order'] = max_order + 1

        milestone = Milestone.objects.create(
            goal=goal,
            **serializer.validated_data
        )

        return Response(
            MilestoneSerializer(milestone).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(summary="Log progress for a goal")
    @action(detail=True, methods=['post'])
    def log_progress(self, request, pk=None):
        """Log progress for a goal."""
        goal = self.get_object()
        serializer = ProgressLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        log = GoalProgressLog.objects.create(
            goal=goal,
            **serializer.validated_data
        )

        return Response(
            GoalProgressLogSerializer(log).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(summary="Get goal statistics")
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get goal statistics for the current user."""
        goals = self.get_queryset()

        stats = {
            'total': goals.count(),
            'by_status': {
                'not_started': goals.filter(status='not_started').count(),
                'in_progress': goals.filter(status='in_progress').count(),
                'completed': goals.filter(status='completed').count(),
                'on_hold': goals.filter(status='on_hold').count(),
                'abandoned': goals.filter(status='abandoned').count(),
            },
            'by_category': {},
            'overdue': goals.filter(
                due_date__lt=timezone.now().date(),
                status__in=['not_started', 'in_progress']
            ).count(),
        }

        for category, _ in Goal.CATEGORY_CHOICES:
            stats['by_category'][category] = goals.filter(category=category).count()

        return Response(stats)


class MilestoneViewSet(viewsets.ModelViewSet):
    """ViewSet for milestones."""
    permission_classes = [IsAuthenticated]
    serializer_class = MilestoneSerializer
    http_method_names = ['get', 'put', 'patch', 'delete']

    def get_queryset(self):
        return Milestone.objects.filter(goal__user=self.request.user)

    @extend_schema(summary="Toggle milestone completion")
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle milestone completion status."""
        milestone = self.get_object()
        milestone.toggle_complete()
        return Response(MilestoneSerializer(milestone).data)
