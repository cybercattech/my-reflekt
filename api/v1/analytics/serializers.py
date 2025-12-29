"""
Analytics serializers for the Reflekt API.
"""
from rest_framework import serializers
from apps.analytics.models import (
    EntryAnalysis, MonthlySnapshot, YearlyReview,
    TrackedBook, TrackedPerson, CaptureSnapshot
)
from apps.journal.models import EntryCapture


class EntryAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for entry analysis."""
    entry_date = serializers.DateField(source='entry.entry_date', read_only=True)

    class Meta:
        model = EntryAnalysis
        fields = [
            'id', 'entry_date', 'sentiment_score', 'sentiment_label',
            'detected_mood', 'mood_confidence',
            'keywords', 'themes', 'summary',
            'moon_phase', 'moon_illumination',
            'weather_condition', 'weather_description',
            'temperature', 'humidity',
            'zodiac_sign', 'analyzed_at'
        ]
        read_only_fields = ['__all__']


class MonthlySnapshotSerializer(serializers.ModelSerializer):
    """Serializer for monthly snapshots."""
    month_name = serializers.CharField(read_only=True)

    class Meta:
        model = MonthlySnapshot
        fields = [
            'id', 'year', 'month', 'month_name',
            'entry_count', 'total_words', 'avg_sentiment',
            'dominant_mood', 'mood_distribution', 'top_themes',
            'best_day_id', 'best_day_sentiment',
            'worst_day_id', 'worst_day_sentiment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['__all__']


class YearlyReviewSerializer(serializers.ModelSerializer):
    """Serializer for yearly reviews."""

    class Meta:
        model = YearlyReview
        fields = [
            'id', 'year', 'total_entries', 'total_words',
            'avg_sentiment', 'dominant_mood',
            'mood_distribution', 'monthly_trend',
            'top_themes', 'theme_sentiments',
            'highlights', 'lowlights',
            'narrative_summary', 'insights',
            'generated_at'
        ]
        read_only_fields = ['__all__']


class TrackedBookSerializer(serializers.ModelSerializer):
    """Serializer for tracked books."""
    progress_percentage = serializers.IntegerField(read_only=True)
    status_icon = serializers.CharField(read_only=True)
    star_rating_display = serializers.CharField(read_only=True)

    class Meta:
        model = TrackedBook
        fields = [
            'id', 'title', 'author', 'status',
            'started_date', 'finished_date',
            'current_page', 'total_pages', 'progress_percentage',
            'rating', 'star_rating_display', 'status_icon',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TrackedPersonSerializer(serializers.ModelSerializer):
    """Serializer for tracked people."""
    relationship_icon = serializers.CharField(read_only=True)

    class Meta:
        model = TrackedPerson
        fields = [
            'id', 'name', 'relationship', 'sentiment', 'notes',
            'mention_count', 'first_mention_date', 'last_mention_date',
            'relationship_icon', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'mention_count', 'first_mention_date',
            'last_mention_date', 'created_at', 'updated_at'
        ]


class CaptureSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for capture snapshots."""

    class Meta:
        model = CaptureSnapshot
        fields = [
            'id', 'year', 'month', 'capture_type',
            'count', 'data', 'created_at', 'updated_at'
        ]
        read_only_fields = ['__all__']


class EntryCaptureListSerializer(serializers.ModelSerializer):
    """Serializer for listing captures."""
    entry_date = serializers.DateField(source='entry.entry_date', read_only=True)
    display_text = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)

    class Meta:
        model = EntryCapture
        fields = [
            'id', 'capture_type', 'data', 'display_text', 'icon',
            'entry_date', 'created_at'
        ]
        read_only_fields = ['__all__']


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics."""
    total_entries = serializers.IntegerField()
    total_words = serializers.IntegerField()
    avg_sentiment = serializers.FloatField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    mood_distribution = serializers.DictField()
    entries_this_month = serializers.IntegerField()
    entries_this_year = serializers.IntegerField()
    top_themes = serializers.ListField()
