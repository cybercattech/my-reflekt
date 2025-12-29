"""
API v1 URL configuration.
"""
from django.urls import path, include

app_name = 'v1'

urlpatterns = [
    path('auth/', include('api.v1.auth.urls')),
    path('journal/', include('api.v1.journal.urls')),
    path('analytics/', include('api.v1.analytics.urls')),
    path('goals/', include('api.v1.goals.urls')),
    path('habits/', include('api.v1.habits.urls')),
    path('friends/', include('api.v1.friends.urls')),
]
