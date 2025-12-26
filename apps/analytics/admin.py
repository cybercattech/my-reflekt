from django.contrib import admin
from .models import (
    EntryAnalysis, MonthlySnapshot, YearlyReview,
    TrackedBook, TrackedPerson, CaptureSnapshot
)


@admin.register(EntryAnalysis)
class EntryAnalysisAdmin(admin.ModelAdmin):
    list_display = ('entry', 'sentiment_score', 'sentiment_label', 'detected_mood', 'analyzed_at')
    list_filter = ('sentiment_label', 'detected_mood')
    search_fields = ('entry__user__email', 'entry__title')
    readonly_fields = ('analyzed_at',)


@admin.register(MonthlySnapshot)
class MonthlySnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'month', 'entry_count', 'avg_sentiment', 'dominant_mood')
    list_filter = ('year', 'month', 'dominant_mood')
    search_fields = ('user__email',)


@admin.register(YearlyReview)
class YearlyReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'total_entries', 'avg_sentiment', 'dominant_mood', 'generated_at')
    list_filter = ('year', 'dominant_mood')
    search_fields = ('user__email',)


@admin.register(TrackedBook)
class TrackedBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'author', 'status', 'started_date', 'finished_date', 'rating')
    list_filter = ('status', 'rating')
    search_fields = ('title', 'author', 'user__email')
    readonly_fields = ('normalized_title', 'normalized_author', 'created_at', 'updated_at')
    raw_id_fields = ('user',)


@admin.register(TrackedPerson)
class TrackedPersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'relationship', 'mention_count', 'first_mention_date', 'last_mention_date')
    list_filter = ('relationship',)
    search_fields = ('name', 'user__email')
    readonly_fields = ('normalized_name', 'mention_count')
    raw_id_fields = ('user',)


@admin.register(CaptureSnapshot)
class CaptureSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'capture_type', 'year', 'month', 'count')
    list_filter = ('capture_type', 'year', 'month')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
