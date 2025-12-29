"""
Goals serializers for the Reflekt API.
"""
from rest_framework import serializers
from apps.goals.models import Goal, Milestone, GoalProgressLog


class MilestoneSerializer(serializers.ModelSerializer):
    """Serializer for goal milestones."""

    class Meta:
        model = Milestone
        fields = [
            'id', 'title', 'description', 'order', 'due_date',
            'is_completed', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'completed_at', 'created_at', 'updated_at']


class GoalProgressLogSerializer(serializers.ModelSerializer):
    """Serializer for goal progress logs."""

    class Meta:
        model = GoalProgressLog
        fields = ['id', 'value', 'note', 'logged_at']
        read_only_fields = ['id', 'logged_at']


class GoalListSerializer(serializers.ModelSerializer):
    """Serializer for goal list view."""
    progress_percentage = serializers.FloatField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    milestone_count = serializers.SerializerMethodField()
    completed_milestone_count = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            'id', 'title', 'category', 'priority', 'status',
            'target_value', 'current_value', 'unit',
            'start_date', 'due_date',
            'progress_percentage', 'days_remaining', 'is_overdue',
            'milestone_count', 'completed_milestone_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_milestone_count(self, obj):
        return obj.milestones.count()

    def get_completed_milestone_count(self, obj):
        return obj.milestones.filter(is_completed=True).count()


class GoalDetailSerializer(serializers.ModelSerializer):
    """Serializer for goal detail view."""
    progress_percentage = serializers.FloatField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    status_color = serializers.CharField(read_only=True)
    priority_color = serializers.CharField(read_only=True)
    category_icon = serializers.CharField(read_only=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    progress_logs = GoalProgressLogSerializer(many=True, read_only=True)

    class Meta:
        model = Goal
        fields = [
            'id', 'title', 'description',
            'success_criteria', 'target_value', 'current_value', 'unit',
            'why_achievable', 'relevance',
            'start_date', 'due_date',
            'category', 'priority', 'status',
            'progress_percentage', 'days_remaining', 'is_overdue',
            'status_color', 'priority_color', 'category_icon',
            'milestones', 'progress_logs',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals."""
    milestones = MilestoneSerializer(many=True, required=False)

    class Meta:
        model = Goal
        fields = [
            'title', 'description',
            'success_criteria', 'target_value', 'unit',
            'why_achievable', 'relevance',
            'start_date', 'due_date',
            'category', 'priority', 'status',
            'milestones'
        ]

    def create(self, validated_data):
        milestones_data = validated_data.pop('milestones', [])
        user = self.context['request'].user

        goal = Goal.objects.create(user=user, **validated_data)

        for idx, milestone_data in enumerate(milestones_data):
            milestone_data['order'] = idx
            Milestone.objects.create(goal=goal, **milestone_data)

        return goal


class GoalUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating goals."""

    class Meta:
        model = Goal
        fields = [
            'title', 'description',
            'success_criteria', 'target_value', 'current_value', 'unit',
            'why_achievable', 'relevance',
            'start_date', 'due_date',
            'category', 'priority', 'status'
        ]


class MilestoneCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating milestones."""

    class Meta:
        model = Milestone
        fields = ['title', 'description', 'order', 'due_date']


class ProgressLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for logging progress."""

    class Meta:
        model = GoalProgressLog
        fields = ['value', 'note']
