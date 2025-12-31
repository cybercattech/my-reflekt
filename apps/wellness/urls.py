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

    # API endpoints
    path('api/pain/log/', views.api_pain_log, name='api_pain_log'),
    path('api/pain/<int:pk>/delete/', views.api_pain_delete, name='api_pain_delete'),
    path('api/intimacy/log/', views.api_intimacy_log, name='api_intimacy_log'),
    path('api/cycle/log/', views.api_cycle_log, name='api_cycle_log'),
    path('api/correlations/', views.api_correlations, name='api_correlations'),
]
