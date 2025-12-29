"""
Journal serializers for the Reflekt API.
"""
from rest_framework import serializers
from django.contrib.auth.models import User

from apps.journal.models import (
    Entry, Tag, Attachment, EntryCapture,
    SharedPOV, SharedPOVRecipient, POVReply
)
from apps.analytics.models import EntryAnalysis


class TagSerializer(serializers.ModelSerializer):
    """Serializer for journal tags."""

    class Meta:
        model = Tag
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for entry attachments."""
    url = serializers.SerializerMethodField()
    size_display = serializers.CharField(read_only=True)

    class Meta:
        model = Attachment
        fields = [
            'id', 'file', 'url', 'file_type', 'file_name',
            'file_size', 'size_display', 'mime_type', 'created_at'
        ]
        read_only_fields = ['id', 'url', 'size_display', 'created_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class EntryCaptureSerializer(serializers.ModelSerializer):
    """Serializer for entry captures (books, workouts, etc.)."""
    display_text = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)

    class Meta:
        model = EntryCapture
        fields = ['id', 'capture_type', 'data', 'display_text', 'icon', 'created_at']
        read_only_fields = ['id', 'display_text', 'icon', 'created_at']


class EntryAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for AI analysis of entries."""

    class Meta:
        model = EntryAnalysis
        fields = [
            'id', 'sentiment_score', 'sentiment_label',
            'detected_mood', 'mood_confidence',
            'keywords', 'themes', 'summary',
            'moon_phase', 'moon_illumination',
            'weather_condition', 'weather_description',
            'temperature', 'humidity',
            'zodiac_sign', 'analyzed_at'
        ]
        read_only_fields = ['__all__']


class EntryListSerializer(serializers.ModelSerializer):
    """Serializer for entry list view (minimal data)."""
    mood_emoji = serializers.CharField(read_only=True)
    preview = serializers.CharField(read_only=True)
    attachment_count = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Entry
        fields = [
            'id', 'title', 'content', 'preview', 'word_count',
            'mood', 'mood_emoji', 'energy',
            'entry_date', 'created_at', 'is_analyzed',
            'attachment_count', 'tags'
        ]
        read_only_fields = ['id', 'preview', 'word_count', 'mood_emoji', 'created_at']

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class EntryDetailSerializer(serializers.ModelSerializer):
    """Serializer for entry detail view (full data)."""
    mood_emoji = serializers.CharField(read_only=True)
    preview = serializers.CharField(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    captures = EntryCaptureSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    analysis = serializers.SerializerMethodField()

    class Meta:
        model = Entry
        fields = [
            'id', 'title', 'content', 'preview', 'word_count',
            'mood', 'mood_emoji', 'energy',
            'city', 'country_code',
            'entry_date', 'created_at', 'updated_at', 'is_analyzed',
            'attachments', 'captures', 'tags', 'analysis'
        ]
        read_only_fields = [
            'id', 'preview', 'word_count', 'mood_emoji',
            'created_at', 'updated_at', 'is_analyzed'
        ]

    def get_analysis(self, obj):
        try:
            analysis = obj.analysis
            return EntryAnalysisSerializer(analysis).data
        except EntryAnalysis.DoesNotExist:
            return None


class EntryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating entries."""
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True
    )

    class Meta:
        model = Entry
        fields = [
            'title', 'content', 'mood', 'energy',
            'city', 'country_code', 'entry_date', 'tag_names'
        ]

    def create(self, validated_data):
        tag_names = validated_data.pop('tag_names', [])
        user = self.context['request'].user

        entry = Entry.objects.create(user=user, **validated_data)

        # Handle tags
        for tag_name in tag_names:
            tag, _ = Tag.objects.get_or_create(user=user, name=tag_name)
            tag.entries.add(entry)

        return entry


class EntryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating entries."""
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True
    )

    class Meta:
        model = Entry
        fields = [
            'title', 'content', 'mood', 'energy',
            'city', 'country_code', 'entry_date', 'tag_names'
        ]

    def update(self, instance, validated_data):
        tag_names = validated_data.pop('tag_names', None)

        # Update entry fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update tags if provided
        if tag_names is not None:
            user = self.context['request'].user
            # Remove existing tags
            instance.tags.clear()
            # Add new tags
            for tag_name in tag_names:
                tag, _ = Tag.objects.get_or_create(user=user, name=tag_name)
                tag.entries.add(instance)

        return instance


# POV Serializers
class POVReplySerializer(serializers.ModelSerializer):
    """Serializer for POV replies."""
    author_email = serializers.CharField(source='author.email', read_only=True)
    author_username = serializers.SerializerMethodField()

    class Meta:
        model = POVReply
        fields = ['id', 'content', 'author_email', 'author_username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author_email', 'author_username', 'created_at', 'updated_at']

    def get_author_username(self, obj):
        profile = getattr(obj.author, 'profile', None)
        return profile.username if profile else None


class SharedPOVRecipientSerializer(serializers.ModelSerializer):
    """Serializer for POV recipients."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    username = serializers.SerializerMethodField()

    class Meta:
        model = SharedPOVRecipient
        fields = ['id', 'user_email', 'username', 'is_read', 'read_at', 'created_at']
        read_only_fields = ['id', 'user_email', 'username', 'created_at']

    def get_username(self, obj):
        profile = getattr(obj.user, 'profile', None)
        return profile.username if profile else None


class SharedPOVListSerializer(serializers.ModelSerializer):
    """Serializer for POV list view."""
    author_email = serializers.CharField(source='author.email', read_only=True)
    author_username = serializers.SerializerMethodField()
    entry_date = serializers.DateField(source='entry.entry_date', read_only=True)
    preview = serializers.CharField(read_only=True)
    reply_count = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = SharedPOV
        fields = [
            'id', 'preview', 'author_email', 'author_username',
            'entry_date', 'reply_count', 'is_read', 'created_at'
        ]

    def get_author_username(self, obj):
        profile = getattr(obj.author, 'profile', None)
        return profile.username if profile else None

    def get_reply_count(self, obj):
        return obj.replies.count()

    def get_is_read(self, obj):
        request = self.context.get('request')
        if request:
            recipient = obj.recipients.filter(user=request.user).first()
            return recipient.is_read if recipient else True
        return True


class SharedPOVDetailSerializer(serializers.ModelSerializer):
    """Serializer for POV detail view."""
    author_email = serializers.CharField(source='author.email', read_only=True)
    author_username = serializers.SerializerMethodField()
    entry_date = serializers.DateField(source='entry.entry_date', read_only=True)
    recipients = SharedPOVRecipientSerializer(many=True, read_only=True)
    replies = POVReplySerializer(many=True, read_only=True)

    class Meta:
        model = SharedPOV
        fields = [
            'id', 'content', 'author_email', 'author_username',
            'entry_date', 'recipients', 'replies',
            'created_at', 'updated_at'
        ]

    def get_author_username(self, obj):
        profile = getattr(obj.author, 'profile', None)
        return profile.username if profile else None


class POVReplyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating POV replies."""

    class Meta:
        model = POVReply
        fields = ['content']

    def create(self, validated_data):
        pov = self.context['pov']
        user = self.context['request'].user

        return POVReply.objects.create(
            pov=pov,
            author=user,
            **validated_data
        )
