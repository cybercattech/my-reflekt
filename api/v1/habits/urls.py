"""
Habits URL patterns for the Reflekt API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import HabitViewSet

router = DefaultRouter()
router.register('', HabitViewSet, basename='habit')

urlpatterns = [
    path('', include(router.urls)),
]
