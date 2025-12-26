from django.contrib import admin
from .models import Goal, Milestone, GoalProgressLog


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    fields = ['title', 'order', 'due_date', 'is_completed', 'completed_at']
    readonly_fields = ['completed_at']


class GoalProgressLogInline(admin.TabularInline):
    model = GoalProgressLog
    extra = 0
    readonly_fields = ['logged_at']
    max_num = 10


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'status', 'priority', 'due_date', 'progress_percentage']
    list_filter = ['status', 'category', 'priority', 'user']
    search_fields = ['title', 'description', 'user__username', 'user__email']
    date_hierarchy = 'created_at'
    inlines = [MilestoneInline, GoalProgressLogInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'title', 'description', 'category', 'priority', 'status')
        }),
        ('SMART Details', {
            'fields': ('success_criteria', 'target_value', 'current_value', 'unit',
                       'why_achievable', 'relevance'),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': ('start_date', 'due_date')
        }),
        ('Journal Integration', {
            'fields': ('journal_entries',),
            'classes': ('collapse',)
        }),
        ('Linked Habits', {
            'fields': ('linked_habits',),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ['journal_entries', 'linked_habits']


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['title', 'goal', 'order', 'is_completed', 'due_date']
    list_filter = ['is_completed', 'goal__user']
    search_fields = ['title', 'goal__title']


@admin.register(GoalProgressLog)
class GoalProgressLogAdmin(admin.ModelAdmin):
    list_display = ['goal', 'value', 'logged_at']
    list_filter = ['goal__user', 'logged_at']
    search_fields = ['goal__title', 'note']
    date_hierarchy = 'logged_at'
