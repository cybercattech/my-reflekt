"""
Goals URL patterns for the Reflekt API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import GoalViewSet, MilestoneViewSet

router = DefaultRouter()
router.register('', GoalViewSet, basename='goal')
router.register('milestones', MilestoneViewSet, basename='milestone')

urlpatterns = [
    path('', include(router.urls)),
]
