from django.urls import path
from . import views

app_name = 'goals'

urlpatterns = [
    # Goal CRUD
    path('', views.goal_list, name='goal_list'),
    path('new/', views.goal_create, name='goal_create'),
    path('<int:pk>/', views.goal_detail, name='goal_detail'),
    path('<int:pk>/edit/', views.goal_edit, name='goal_edit'),
    path('<int:pk>/delete/', views.goal_delete, name='goal_delete'),

    # Progress tracking
    path('<int:pk>/progress/', views.goal_update_progress, name='goal_update_progress'),

    # Milestones
    path('<int:goal_pk>/milestones/add/', views.milestone_create, name='milestone_create'),
    path('milestones/<int:pk>/toggle/', views.milestone_toggle, name='milestone_toggle'),
    path('milestones/<int:pk>/delete/', views.milestone_delete, name='milestone_delete'),

    # Journal entry linking
    path('<int:pk>/link-entry/', views.goal_link_entry, name='goal_link_entry'),
    path('<int:pk>/unlink-entry/', views.goal_unlink_entry, name='goal_unlink_entry'),
    path('<int:pk>/search-entries/', views.goal_entries_search, name='goal_entries_search'),

    # Habit linking
    path('<int:pk>/search-habits/', views.goal_habits_search, name='goal_habits_search'),
    path('<int:pk>/link-habit/', views.goal_link_habit, name='goal_link_habit'),
    path('<int:pk>/unlink-habit/', views.goal_unlink_habit, name='goal_unlink_habit'),
]
