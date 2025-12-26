from django.urls import path
from . import views

app_name = 'habits'

urlpatterns = [
    # Habit CRUD
    path('', views.habit_list, name='habit_list'),
    path('new/', views.habit_create, name='habit_create'),
    path('<int:pk>/', views.habit_detail, name='habit_detail'),
    path('<int:pk>/edit/', views.habit_edit, name='habit_edit'),
    path('<int:pk>/delete/', views.habit_delete, name='habit_delete'),

    # Check-ins
    path('<int:pk>/checkin/', views.habit_checkin, name='habit_checkin'),
    path('<int:pk>/checkin/<str:date_str>/', views.habit_checkin_date, name='habit_checkin_date'),

    # Calendar view
    path('<int:pk>/calendar/', views.habit_calendar, name='habit_calendar'),

    # Journal entry linking
    path('<int:pk>/link-entry/', views.habit_link_entry, name='habit_link_entry'),
    path('<int:pk>/unlink-entry/', views.habit_unlink_entry, name='habit_unlink_entry'),
    path('<int:pk>/search-entries/', views.habit_entries_search, name='habit_entries_search'),
]
