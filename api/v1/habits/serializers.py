"""
Habits serializers for the Reflekt API.
"""
from rest_framework import serializers
from django.utils import timezone
from apps.habits.models import Habit, HabitCheckin


class HabitCheckinSerializer(serializers.ModelSerializer):
    """Serializer for habit checkins."""

    class Meta:
        model = HabitCheckin
        fields = ['id', 'check_date', 'completed', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class HabitListSerializer(serializers.ModelSerializer):
    """Serializer for habit list view."""
    frequency_display = serializers.CharField(read_only=True)
    completion_rate = serializers.SerializerMethodField()
    is_due_today = serializers.SerializerMethodField()
    is_completed_today = serializers.SerializerMethodField()

    class Meta:
        model = Habit
        fields = [
            'id', 'name', 'icon', 'color', 'category',
            'frequency_type', 'frequency_display',
            'current_streak', 'longest_streak', 'total_completions',
            'is_active', 'is_due_today', 'is_completed_today',
            'completion_rate', 'last_completed_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_streak', 'longest_streak', 'total_completions', 'created_at', 'updated_at']

    def get_completion_rate(self, obj):
        return round(obj.get_completion_rate(days=30), 1)

    def get_is_due_today(self, obj):
        return obj.is_due_on_date(timezone.now().date())

    def get_is_completed_today(self, obj):
        return obj.is_completed_on_date(timezone.now().date())


class HabitDetailSerializer(serializers.ModelSerializer):
    """Serializer for habit detail view."""
    frequency_display = serializers.CharField(read_only=True)
    category_icon = serializers.CharField(read_only=True)
    completion_rate = serializers.SerializerMethodField()
    is_due_today = serializers.SerializerMethodField()
    is_completed_today = serializers.SerializerMethodField()
    recent_checkins = serializers.SerializerMethodField()

    class Meta:
        model = Habit
        fields = [
            'id', 'name', 'description', 'icon', 'color', 'category', 'category_icon',
            'frequency_type', 'times_per_week', 'specific_days', 'frequency_display',
            'start_date', 'is_active',
            'current_streak', 'longest_streak', 'total_completions',
            'last_completed_date', 'completion_rate',
            'is_due_today', 'is_completed_today',
            'recent_checkins',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_streak', 'longest_streak', 'total_completions',
            'last_completed_date', 'created_at', 'updated_at'
        ]

    def get_completion_rate(self, obj):
        return round(obj.get_completion_rate(days=30), 1)

    def get_is_due_today(self, obj):
        return obj.is_due_on_date(timezone.now().date())

    def get_is_completed_today(self, obj):
        return obj.is_completed_on_date(timezone.now().date())

    def get_recent_checkins(self, obj):
        checkins = obj.checkins.all()[:30]
        return HabitCheckinSerializer(checkins, many=True).data


class HabitCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating habits."""

    class Meta:
        model = Habit
        fields = [
            'name', 'description', 'icon', 'color', 'category',
            'frequency_type', 'times_per_week', 'specific_days',
            'start_date', 'is_active'
        ]

    def validate(self, attrs):
        frequency_type = attrs.get('frequency_type', 'daily')

        if frequency_type == 'x_per_week':
            times_per_week = attrs.get('times_per_week', 1)
            if times_per_week < 1 or times_per_week > 7:
                raise serializers.ValidationError({
                    'times_per_week': 'Must be between 1 and 7.'
                })

        if frequency_type == 'specific_days':
            specific_days = attrs.get('specific_days', '')
            if not specific_days:
                raise serializers.ValidationError({
                    'specific_days': 'Required for specific days frequency.'
                })
            # Validate day numbers
            try:
                days = [int(d) for d in specific_days.split(',')]
                if not all(0 <= d <= 6 for d in days):
                    raise ValueError()
            except ValueError:
                raise serializers.ValidationError({
                    'specific_days': 'Must be comma-separated day numbers (0-6).'
                })

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        return Habit.objects.create(user=user, **validated_data)


class HabitUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating habits."""

    class Meta:
        model = Habit
        fields = [
            'name', 'description', 'icon', 'color', 'category',
            'frequency_type', 'times_per_week', 'specific_days',
            'is_active'
        ]


class HabitCheckinCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating checkins."""

    class Meta:
        model = HabitCheckin
        fields = ['check_date', 'completed', 'note']

    def create(self, validated_data):
        habit = self.context['habit']
        check_date = validated_data.get('check_date', timezone.now().date())

        # Get or create checkin for this date
        checkin, created = HabitCheckin.objects.update_or_create(
            habit=habit,
            check_date=check_date,
            defaults={
                'completed': validated_data.get('completed', True),
                'note': validated_data.get('note', '')
            }
        )

        return checkin
