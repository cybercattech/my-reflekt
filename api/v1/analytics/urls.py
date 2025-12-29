"""
Analytics URL patterns for the Reflekt API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardView, MonthlySnapshotView, MonthlySnapshotListView,
    YearlyReviewView, CapturesListView,
    TrackedBookViewSet, TrackedPersonViewSet,
    SentimentTrendView, MoodDistributionView
)

router = DefaultRouter()
router.register('books', TrackedBookViewSet, basename='tracked_book')
router.register('people', TrackedPersonViewSet, basename='tracked_person')

urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # Monthly/Yearly analytics
    path('monthly/', MonthlySnapshotListView.as_view(), name='monthly_list'),
    path('monthly/<int:year>/<int:month>/', MonthlySnapshotView.as_view(), name='monthly_detail'),
    path('yearly/<int:year>/', YearlyReviewView.as_view(), name='yearly_review'),

    # Captures
    path('captures/', CapturesListView.as_view(), name='captures'),

    # Charts data
    path('sentiment-trend/', SentimentTrendView.as_view(), name='sentiment_trend'),
    path('mood-distribution/', MoodDistributionView.as_view(), name='mood_distribution'),

    # Tracked entities
    path('', include(router.urls)),
]
