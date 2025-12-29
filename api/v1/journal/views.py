"""
Journal views for the Reflekt API.
"""
from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.journal.models import (
    Entry, Tag, Attachment, EntryCapture,
    SharedPOV, SharedPOVRecipient, POVReply
)
from api.permissions import IsOwner
from api.pagination import JournalEntryCursorPagination, StandardResultsPagination

from .serializers import (
    EntryListSerializer, EntryDetailSerializer,
    EntryCreateSerializer, EntryUpdateSerializer,
    TagSerializer, AttachmentSerializer, EntryCaptureSerializer,
    SharedPOVListSerializer, SharedPOVDetailSerializer,
    POVReplySerializer, POVReplyCreateSerializer
)


class EntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for journal entries.

    Provides CRUD operations for journal entries.
    """
    permission_classes = [IsAuthenticated, IsOwner]
    pagination_class = JournalEntryCursorPagination

    def get_queryset(self):
        """Return entries for the current user only."""
        return Entry.objects.filter(user=self.request.user).prefetch_related(
            'attachments', 'captures', 'tags'
        ).select_related('user')

    def get_serializer_class(self):
        if self.action == 'list':
            return EntryListSerializer
        if self.action in ['create']:
            return EntryCreateSerializer
        if self.action in ['update', 'partial_update']:
            return EntryUpdateSerializer
        return EntryDetailSerializer

    @extend_schema(
        summary="List journal entries",
        description="Get paginated list of journal entries for the current user.",
        parameters=[
            OpenApiParameter(
                name='mood',
                description='Filter by mood (ecstatic, happy, neutral, sad, angry)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='start_date',
                description='Filter entries from this date (YYYY-MM-DD)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='end_date',
                description='Filter entries until this date (YYYY-MM-DD)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='search',
                description='Search in title and content',
                required=False,
                type=str
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Apply filters
        mood = request.query_params.get('mood')
        if mood:
            queryset = queryset.filter(mood=mood)

        start_date = request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(entry_date__gte=start_date)

        end_date = request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(entry_date__lte=end_date)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        self.queryset = queryset
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a journal entry")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get a journal entry")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a journal entry")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partially update a journal entry")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete a journal entry")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Upload attachment to entry",
        description="Upload an image, audio, or video file to a journal entry."
    )
    @action(
        detail=True,
        methods=['post'],
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_attachment(self, request, pk=None):
        """Upload an attachment to an entry."""
        entry = self.get_object()
        file = request.FILES.get('file')

        if not file:
            return Response(
                {'error': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine file type
        mime_type = file.content_type
        if mime_type.startswith('image/'):
            file_type = 'image'
        elif mime_type.startswith('audio/'):
            file_type = 'audio'
        elif mime_type.startswith('video/'):
            file_type = 'video'
        else:
            return Response(
                {'error': 'Unsupported file type.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attachment = Attachment.objects.create(
            entry=entry,
            file=file,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size,
            mime_type=mime_type
        )

        serializer = AttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Get entries for a specific month")
    @action(detail=False, methods=['get'])
    def by_month(self, request):
        """Get entries for a specific month."""
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not year or not month:
            return Response(
                {'error': 'year and month parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(
            entry_date__year=int(year),
            entry_date__month=int(month)
        )

        serializer = EntryListSerializer(queryset, many=True)
        return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet for user tags."""
    permission_classes = [IsAuthenticated]
    serializer_class = TagSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet for attachments (delete only, upload via entry)."""
    permission_classes = [IsAuthenticated]
    serializer_class = AttachmentSerializer
    http_method_names = ['get', 'delete']  # Only allow get and delete

    def get_queryset(self):
        return Attachment.objects.filter(entry__user=self.request.user)


# POV Views
class ReceivedPOVListView(generics.ListAPIView):
    """List POVs received by the current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = SharedPOVListSerializer
    pagination_class = StandardResultsPagination

    @extend_schema(summary="List received POVs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return SharedPOV.objects.filter(
            recipients__user=self.request.user
        ).select_related('author', 'entry').prefetch_related(
            'recipients', 'replies'
        ).order_by('-created_at')


class SentPOVListView(generics.ListAPIView):
    """List POVs sent by the current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = SharedPOVListSerializer
    pagination_class = StandardResultsPagination

    @extend_schema(summary="List sent POVs")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return SharedPOV.objects.filter(
            author=self.request.user
        ).select_related('author', 'entry').prefetch_related(
            'recipients', 'replies'
        ).order_by('-created_at')


class POVDetailView(generics.RetrieveAPIView):
    """Get POV detail."""
    permission_classes = [IsAuthenticated]
    serializer_class = SharedPOVDetailSerializer

    @extend_schema(summary="Get POV detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """User can see POVs they authored or received."""
        return SharedPOV.objects.filter(
            Q(author=self.request.user) | Q(recipients__user=self.request.user)
        ).distinct().select_related('author', 'entry').prefetch_related(
            'recipients', 'replies'
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Mark as read if user is a recipient
        recipient = instance.recipients.filter(user=request.user).first()
        if recipient and not recipient.is_read:
            recipient.is_read = True
            recipient.read_at = timezone.now()
            recipient.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class POVReplyView(generics.CreateAPIView):
    """Reply to a POV."""
    permission_classes = [IsAuthenticated]
    serializer_class = POVReplyCreateSerializer

    @extend_schema(summary="Reply to a POV")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        pov_id = self.kwargs.get('pk')
        pov = SharedPOV.objects.filter(
            Q(author=self.request.user) | Q(recipients__user=self.request.user),
            id=pov_id
        ).first()

        if not pov:
            from rest_framework.exceptions import NotFound
            raise NotFound("POV not found or you don't have access.")

        context['pov'] = pov
        return context


class MarkPOVReadView(generics.GenericAPIView):
    """Mark a POV as read."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Mark POV as read")
    def post(self, request, pk):
        recipient = SharedPOVRecipient.objects.filter(
            pov_id=pk,
            user=request.user
        ).first()

        if not recipient:
            return Response(
                {'error': 'POV not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not recipient.is_read:
            recipient.is_read = True
            recipient.read_at = timezone.now()
            recipient.save()

        return Response({'message': 'Marked as read.'})
