from django.contrib import admin
from .models import Habit, HabitCheckin


class HabitCheckinInline(admin.TabularInline):
    model = HabitCheckin
    extra = 0
    readonly_fields = ['created_at']
    ordering = ['-check_date']
    max_num = 30


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'category', 'frequency_type', 'is_active', 'current_streak', 'total_completions']
    list_filter = ['is_active', 'category', 'frequency_type', 'user']
    search_fields = ['name', 'description', 'user__username', 'user__email']
    date_hierarchy = 'created_at'
    inlines = [HabitCheckinInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'name', 'description', 'icon', 'color', 'category')
        }),
        ('Frequency', {
            'fields': ('frequency_type', 'times_per_week', 'specific_days', 'start_date', 'is_active')
        }),
        ('Stats (Read Only)', {
            'fields': ('current_streak', 'longest_streak', 'total_completions', 'last_completed_date'),
            'classes': ('collapse',)
        }),
        ('Journal Integration', {
            'fields': ('journal_entries',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['current_streak', 'longest_streak', 'total_completions', 'last_completed_date']
    filter_horizontal = ['journal_entries']


@admin.register(HabitCheckin)
class HabitCheckinAdmin(admin.ModelAdmin):
    list_display = ['habit', 'check_date', 'completed', 'journal_entry']
    list_filter = ['completed', 'check_date', 'habit__user']
    search_fields = ['habit__name', 'note']
    date_hierarchy = 'check_date'
    raw_id_fields = ['journal_entry']
