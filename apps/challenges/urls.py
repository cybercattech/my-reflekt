"""
URL routes for the Challenges app.
"""
from django.urls import path
from . import views

app_name = 'challenges'

urlpatterns = [
    # Browse challenges
    path('', views.challenge_list, name='list'),
    path('<slug:slug>/', views.challenge_detail, name='detail'),

    # Participation
    path('<slug:slug>/join/', views.join_challenge, name='join'),
    path('<slug:slug>/progress/', views.challenge_progress, name='progress'),
    path('<slug:slug>/abandon/', views.abandon_challenge, name='abandon'),

    # Entry submission
    path('<slug:slug>/day/<int:day_number>/submit/', views.submit_challenge_entry, name='submit_entry'),

    # API endpoints
    path('api/active/', views.get_active_challenges_api, name='active_challenges_api'),
]
