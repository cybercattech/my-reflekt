from django.urls import path
from . import views

app_name = 'wellness'

urlpatterns = [
    # Main dashboards
    path('', views.wellness_dashboard, name='dashboard'),
    path('pain/', views.pain_dashboard, name='pain'),
    path('pain/log/', views.pain_quick_log, name='pain_log'),
    path('intimacy/', views.intimacy_dashboard, name='intimacy'),
    path('cycle/', views.cycle_dashboard, name='cycle'),
    path('cycle/calendar/', views.cycle_calendar, name='cycle_calendar'),

    # Fitness tracking
    path('fitness/', views.fitness_dashboard, name='fitness_dashboard'),
    path('fitness/body/', views.body_metrics, name='body_metrics'),
    path('fitness/cardio/', views.cardio_log_view, name='cardio_log'),
    path('fitness/goals/', views.fitness_goals, name='fitness_goals'),
    path('fitness/goals/create/', views.create_fitness_goal, name='create_fitness_goal'),
    path('fitness/goals/<int:pk>/', views.fitness_goal_detail, name='fitness_goal_detail'),
    path('fitness/goals/<int:pk>/edit/', views.edit_fitness_goal, name='edit_fitness_goal'),
    path('fitness/goals/<int:pk>/delete/', views.delete_fitness_goal, name='delete_fitness_goal'),

    # API endpoints - existing
    path('api/pain/log/', views.api_pain_log, name='api_pain_log'),
    path('api/pain/<int:pk>/delete/', views.api_pain_delete, name='api_pain_delete'),
    path('api/intimacy/log/', views.api_intimacy_log, name='api_intimacy_log'),
    path('api/cycle/log/', views.api_cycle_log, name='api_cycle_log'),
    path('api/correlations/', views.api_correlations, name='api_correlations'),

    # API endpoints - fitness
    path('api/fitness/body/log/', views.api_log_body_metric, name='api_log_body_metric'),
    path('api/fitness/body/<int:pk>/delete/', views.api_delete_body_metric, name='api_delete_body_metric'),
    path('api/fitness/cardio/log/', views.api_log_cardio, name='api_log_cardio'),
    path('api/fitness/cardio/<int:pk>/delete/', views.api_delete_cardio_log, name='api_delete_cardio_log'),
    path('api/fitness/goals/<int:pk>/progress/', views.api_update_fitness_goal_progress, name='api_update_fitness_goal_progress'),
    path('api/fitness/weight-chart/', views.api_weight_chart_data, name='api_weight_chart'),
    path('api/fitness/cardio-chart/', views.api_cardio_chart_data, name='api_cardio_chart'),
]
