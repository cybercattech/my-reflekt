from django.contrib import admin
from .models import Entry, Tag, EntryCapture, SharedPOV, SharedPOVRecipient, POVReply


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('entry_date', 'user', 'title', 'mood', 'word_count', 'is_analyzed')
    list_filter = ('mood', 'energy', 'is_analyzed', 'entry_date')
    search_fields = ('title', 'content', 'user__email')
    date_hierarchy = 'entry_date'
    readonly_fields = ('word_count', 'created_at', 'updated_at')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    search_fields = ('name', 'user__email')


@admin.register(EntryCapture)
class EntryCaptureAdmin(admin.ModelAdmin):
    list_display = ('capture_type', 'entry', 'created_at')
    list_filter = ('capture_type', 'created_at')
    search_fields = ('entry__title', 'entry__user__email')
    readonly_fields = ('created_at',)
    raw_id_fields = ('entry',)


@admin.register(SharedPOV)
class SharedPOVAdmin(admin.ModelAdmin):
    list_display = ('author', 'entry', 'position_index', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('author__email', 'content', 'entry__title')
    readonly_fields = ('content_hash', 'created_at', 'updated_at')
    raw_id_fields = ('entry', 'author')
    date_hierarchy = 'created_at'


@admin.register(SharedPOVRecipient)
class SharedPOVRecipientAdmin(admin.ModelAdmin):
    list_display = ('pov', 'user', 'is_read', 'email_sent', 'created_at')
    list_filter = ('is_read', 'email_sent', 'created_at')
    search_fields = ('user__email', 'pov__content')
    readonly_fields = ('created_at', 'read_at', 'email_sent_at')
    raw_id_fields = ('pov', 'user')


@admin.register(POVReply)
class POVReplyAdmin(admin.ModelAdmin):
    list_display = ('pov', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('author__email', 'content')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('pov', 'author')
