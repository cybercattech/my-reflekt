"""
Journal URL patterns for the Reflekt API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EntryViewSet, TagViewSet, AttachmentViewSet,
    ReceivedPOVListView, SentPOVListView,
    POVDetailView, POVReplyView, MarkPOVReadView
)

router = DefaultRouter()
router.register('entries', EntryViewSet, basename='entry')
router.register('tags', TagViewSet, basename='tag')
router.register('attachments', AttachmentViewSet, basename='attachment')

urlpatterns = [
    # Entry and Tag routes
    path('', include(router.urls)),

    # POV routes
    path('pov/received/', ReceivedPOVListView.as_view(), name='pov_received'),
    path('pov/sent/', SentPOVListView.as_view(), name='pov_sent'),
    path('pov/<int:pk>/', POVDetailView.as_view(), name='pov_detail'),
    path('pov/<int:pk>/reply/', POVReplyView.as_view(), name='pov_reply'),
    path('pov/<int:pk>/mark-read/', MarkPOVReadView.as_view(), name='pov_mark_read'),
]
