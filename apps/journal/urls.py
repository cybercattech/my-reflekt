from django.urls import path
from . import views

app_name = 'journal'

urlpatterns = [
    path('', views.entry_list, name='entry_list'),
    path('calendar/', views.yearly_calendar, name='yearly_calendar'),
    path('calendar/<int:year>/', views.yearly_calendar, name='yearly_calendar_year'),
    path('new/', views.entry_create, name='entry_create'),
    path('import/', views.import_entries, name='import_entries'),
    path('<int:pk>/', views.entry_detail, name='entry_detail'),
    path('<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('<int:pk>/delete/', views.entry_delete, name='entry_delete'),

    # AJAX endpoints
    path('api/quick-save/', views.entry_quick_save, name='entry_quick_save'),
    path('api/upload-image/', views.upload_inline_image, name='upload_inline_image'),
    path('api/entry-at-offset/', views.entry_at_offset, name='entry_at_offset'),
    path('api/add-devotion/', views.add_devotion_to_entry, name='add_devotion_to_entry'),

    # Attachment endpoints
    path('<int:entry_pk>/attachments/', views.attachment_list, name='attachment_list'),
    path('<int:entry_pk>/attachments/upload/', views.attachment_upload, name='attachment_upload'),
    path('attachments/<int:pk>/delete/', views.attachment_delete, name='attachment_delete'),
    path('attachments/<int:pk>/view/', views.serve_attachment, name='serve_attachment'),

    # Secure media serving (for inline images)
    path('media/<int:user_id>/<str:filename>', views.serve_media, name='serve_media'),

    # Slash commands API
    path('api/slash-commands/', views.get_slash_commands, name='slash_commands'),
    path('api/active-captures/', views.get_active_captures, name='active_captures'),
    path('api/capture/', views.save_capture, name='save_capture'),
    path('api/capture/<int:pk>/delete/', views.delete_capture, name='delete_capture'),
    path('capture/<int:pk>/delete/', views.delete_capture, name='capture_delete'),
    path('api/capture-count/', views.capture_count, name='capture_count'),
    path('api/entry/<int:entry_pk>/captures/', views.get_entry_captures, name='entry_captures'),
    path('api/goals-search/', views.goals_search, name='goals_search'),
    path('api/habits-search/', views.habits_search, name='habits_search'),
    path('api/habits-detect/', views.habits_detect, name='habits_detect'),
    path('api/people-search/', views.people_search, name='people_search'),
    path('api/people-create/', views.people_create, name='people_create'),
    path('api/people-mention/', views.people_mention, name='people_mention'),
    path('api/books-search/', views.books_search, name='books_search'),
    path('api/books-create/', views.books_create, name='books_create'),
    path('api/link-goal/', views.link_goal, name='link_goal'),
    path('api/link-habit/', views.link_habit, name='link_habit'),
    path('api/complete-task/', views.complete_task, name='complete_task'),
    path('api/analyze-entries/', views.analyze_entries, name='analyze_entries'),

    # Entry Modal API
    path('api/entry/<int:pk>/detail/', views.entry_modal_detail, name='entry_modal_detail'),
    path('api/entry/<int:pk>/update/', views.entry_modal_update, name='entry_modal_update'),

    # POV Sharing
    path('shared/', views.shared_povs_list, name='shared_povs_list'),
    path('shared/<int:pk>/', views.shared_pov_detail, name='shared_pov_detail'),
    path('shared/<int:pk>/view/', views.pov_view_and_redirect, name='pov_view_and_redirect'),
    path('api/pov/<int:pov_id>/reply/', views.pov_reply_create, name='pov_reply_create'),
    path('api/pov/<int:pov_id>/delete/', views.pov_delete_recipient, name='pov_delete_recipient'),
    path('api/pov/unread-count/', views.unread_povs_count, name='unread_povs_count'),
]
