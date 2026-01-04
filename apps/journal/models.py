from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from apps.analytics.services.mood import MOOD_EMOJIS
from .fields import UserEncryptedTextField, UserEncryptedCharField


class Entry(models.Model):
    """
    Core journal entry - the heart of the app.

    Users write entries with optional mood/energy tags.
    Each entry is analyzed asynchronously for sentiment and themes.
    """

    MOOD_CHOICES = [
        ('ecstatic', 'Ecstatic'),
        ('happy', 'Happy'),
        ('neutral', 'Neutral'),
        ('sad', 'Sad'),
        ('angry', 'Angry'),
    ]

    ENERGY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    # Owner
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='entries'
    )

    # Content (Encrypted at rest with per-user keys)
    title = UserEncryptedCharField(max_length=200, blank=True)
    content = UserEncryptedTextField()
    word_count = models.IntegerField(default=0)

    # User-provided metadata (optional - not forced)
    mood = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        blank=True,
        help_text="How are you feeling? (Optional)"
    )
    energy = models.CharField(
        max_length=20,
        choices=ENERGY_CHOICES,
        blank=True,
        help_text="What's your energy level? (Optional)"
    )

    # Location where this entry was written (for weather tracking)
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City where you're writing from (for weather data)"
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        default='US',
        help_text="Two-letter country code"
    )

    # The date this entry is about (may differ from created_at)
    entry_date = models.DateField(default=timezone.now)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Processing status
    is_analyzed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-entry_date', '-created_at']
        verbose_name = 'Entry'
        verbose_name_plural = 'Entries'
        indexes = [
            models.Index(fields=['user', 'entry_date']),
            models.Index(fields=['user', 'is_analyzed']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        if self.title:
            return f"{self.entry_date}: {self.title}"
        return f"{self.entry_date}: Entry"

    def get_absolute_url(self):
        return reverse('journal:entry_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        # Calculate word count before saving
        self.word_count = len(self.content.split()) if self.content else 0
        super().save(*args, **kwargs)

    @property
    def preview(self):
        """Return first 200 characters of content for previews, excluding POV blocks and HTML tags."""
        import re
        from html import unescape
        content = self.content or ''

        # Remove injected POV blocks: ```pov @username ... ``` or ```{pov} @username ... ```
        content = re.sub(r'```(?:\{pov\}|pov)\s*@\w+\s*\n.*?```', '', content, flags=re.DOTALL)

        # Remove author POV blocks: {pov} username ... {/pov}
        content = re.sub(r'\{pov\}\s*[^\n]+\n.*?\{/pov\}', '', content, flags=re.DOTALL | re.IGNORECASE)

        # Strip HTML tags (for Quill editor content)
        content = re.sub(r'<[^>]+>', ' ', content)

        # Decode HTML entities
        content = unescape(content)

        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content).strip()

        if len(content) > 200:
            return content[:200] + '...'
        return content

    @property
    def mood_emoji(self):
        """Return emoji for mood."""
        return MOOD_EMOJIS.get(self.mood, '')

    @property
    def first_image(self):
        """Return the first image thumbnail URL or extract first image URL from content."""
        import re
        import os

        # First check for image attachments (prefer thumbnail)
        first_attachment = self.attachments.filter(file_type='image').first()
        if first_attachment:
            return first_attachment.thumbnail_url

        # Then check content for embedded images (Quill stores as <img src="...">)
        if self.content:
            # Match img tags with src attribute
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', self.content)
            if img_match:
                original_url = img_match.group(1)
                # Convert to thumbnail URL if it's an inline image
                # Pattern: /journal/media/{user_id}/{filename}
                inline_match = re.match(r'/journal/media/(\d+)/([^/]+)$', original_url)
                if inline_match:
                    user_id = inline_match.group(1)
                    filename = inline_match.group(2)
                    # Generate thumbnail URL
                    base_name = os.path.splitext(filename)[0]
                    thumb_filename = f"{base_name}_thumb.jpg"
                    return f"/journal/media/{user_id}/thumbs/{thumb_filename}"
                return original_url

        return None


class Tag(models.Model):
    """
    User-defined tags for organizing entries.

    Tags are user-specific (multi-tenant).
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    name = models.CharField(max_length=50)
    entries = models.ManyToManyField(
        Entry,
        related_name='tags',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'name']
        ordering = ['name']

    def __str__(self):
        return self.name


def attachment_upload_path(instance, filename):
    """Generate upload path: attachments/user_id/year/month/filename"""
    import os
    from datetime import datetime
    ext = os.path.splitext(filename)[1].lower()
    now = datetime.now()
    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in '._-')
    return f'attachments/{instance.entry.user_id}/{now.year}/{now.month:02d}/{safe_name}'


def thumbnail_upload_path(instance, filename):
    """Generate upload path for thumbnails"""
    import os
    from datetime import datetime
    now = datetime.now()
    base, ext = os.path.splitext(filename)
    safe_name = "".join(c for c in base if c.isalnum() or c in '._-')
    return f'thumbnails/{instance.entry.user_id}/{now.year}/{now.month:02d}/{safe_name}_thumb{ext}'


class Attachment(models.Model):
    """
    Media attachments for journal entries.

    Supports images, audio, and video files.
    Files stored in S3 (production) or local filesystem (development).
    """

    ATTACHMENT_TYPES = [
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
    ]

    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to=attachment_upload_path)
    thumbnail = models.ImageField(upload_to=thumbnail_upload_path, blank=True, null=True)
    file_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPES)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="Size in bytes")
    mime_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.file_name} ({self.file_type})"

    @property
    def size_display(self):
        """Return human-readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_image(self):
        return self.file_type == 'image'

    @property
    def is_audio(self):
        return self.file_type == 'audio'

    @property
    def is_video(self):
        return self.file_type == 'video'

    @property
    def secure_url(self):
        """Return a secure URL that goes through Django for access control."""
        return reverse('journal:serve_attachment', kwargs={'pk': self.pk})

    @property
    def thumbnail_url(self):
        """Return URL for thumbnail (for images) or secure_url as fallback."""
        if self.thumbnail:
            return reverse('journal:serve_thumbnail', kwargs={'pk': self.pk})
        return self.secure_url

    def generate_thumbnail(self, max_size=200):
        """Generate a thumbnail for image attachments."""
        if self.file_type != 'image':
            return False

        try:
            from PIL import Image
            from io import BytesIO
            from django.core.files.base import ContentFile
            import os

            # Open the original image
            self.file.seek(0)
            img = Image.open(self.file)

            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Calculate thumbnail size maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save thumbnail to BytesIO
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_io.seek(0)

            # Generate thumbnail filename
            base_name = os.path.splitext(self.file_name)[0]
            thumb_name = f"{base_name}_thumb.jpg"

            # Save thumbnail
            self.thumbnail.save(thumb_name, ContentFile(thumb_io.read()), save=False)
            return True

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Thumbnail generation failed: {e}")
            return False


class EntryCapture(models.Model):
    """
    Structured data captures from slash commands.

    Each capture stores structured data (books, workouts, people, etc.)
    that can be queried for analytics and insights.
    """

    CAPTURE_TYPES = [
        ('book', 'Book'),
        ('watched', 'Watched'),
        ('travel', 'Travel'),
        ('workout', 'Workout'),
        ('person', 'Person'),
        ('place', 'Place'),
        ('meal', 'Meal'),
        ('dream', 'Dream'),
        ('gratitude', 'Gratitude'),
        ('pain', 'Pain'),
        ('intimacy', 'Intimacy'),
        ('cycle', 'Cycle'),
    ]

    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name='captures'
    )
    capture_type = models.CharField(max_length=20, choices=CAPTURE_TYPES)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['entry', 'capture_type']),
            models.Index(fields=['capture_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_capture_type_display()} - {self.entry.entry_date}"

    @property
    def icon(self):
        """Return Bootstrap icon class for capture type."""
        icon_map = {
            'book': 'bi-book',
            'watched': 'bi-film',
            'travel': 'bi-geo-alt',
            'workout': 'bi-heart-pulse',
            'person': 'bi-person',
            'place': 'bi-pin-map',
            'meal': 'bi-cup-hot',
            'dream': 'bi-cloud-moon',
            'gratitude': 'bi-heart',
            'pain': 'bi-bandaid',
            'intimacy': 'bi-flower1',
            'cycle': 'bi-calendar-heart',
        }
        return icon_map.get(self.capture_type, 'bi-tag')

    @property
    def display_text(self):
        """Return formatted display text for the capture."""
        data = self.data
        if self.capture_type == 'book':
            title = data.get('title', 'Unknown')
            author = data.get('author', '')
            status = data.get('status', '')
            rating = '★' * data.get('rating', 0) + '☆' * (5 - data.get('rating', 0)) if data.get('rating') else ''
            text = f'"{title}"'
            if author:
                text += f' by {author}'
            parts = []
            if status:
                parts.append(status.title())
            if data.get('page'):
                parts.append(f"Page {data['page']}")
            if rating:
                parts.append(rating)
            if parts:
                text += f" | {' | '.join(parts)}"
            return text

        elif self.capture_type == 'watched':
            title = data.get('title', 'Unknown')
            media_type = data.get('type', '')
            rating_val = int(data.get('rating', 0) or 0)
            rating = '★' * rating_val + '☆' * (5 - rating_val) if rating_val else ''
            text = f'"{title}"'
            parts = []
            if media_type:
                parts.append(media_type.title())
            if rating:
                parts.append(rating)
            if parts:
                text += f" | {' | '.join(parts)}"
            return text

        elif self.capture_type == 'travel':
            mode = data.get('mode', '').title()
            origin = data.get('origin', '')
            destination = data.get('destination', '')
            return f"{mode}: {origin} → {destination}"

        elif self.capture_type == 'workout':
            workout_type = data.get('type', 'Workout').title()
            duration = data.get('duration', 0)
            intensity = data.get('intensity', '').title()
            parts = [workout_type]
            if duration:
                parts.append(f"{duration} min")
            if intensity:
                parts.append(f"({intensity})")
            return ' - '.join(parts)

        elif self.capture_type == 'person':
            name = data.get('name', 'Someone')
            context = data.get('context', '')
            if context:
                return f"{name} ({context})"
            return name

        elif self.capture_type == 'place':
            name = data.get('name', 'Somewhere')
            place_type = data.get('type', '')
            if place_type:
                return f"{name} ({place_type})"
            return name

        elif self.capture_type == 'meal':
            meal = data.get('meal', '').title()
            what = data.get('what', '')
            if meal and what:
                return f"{meal}: {what}"
            return what or meal or 'Meal'

        elif self.capture_type == 'dream':
            return 'Dream entry'

        elif self.capture_type == 'gratitude':
            items = data.get('items', [])
            if items:
                return ', '.join(items[:3])
            return 'Gratitude'

        elif self.capture_type == 'pain':
            location = data.get('location', '').title()
            intensity = data.get('intensity', 0)
            pain_type = data.get('pain_type', '').title()
            parts = []
            if location:
                parts.append(location)
            if intensity:
                parts.append(f"{intensity}/10")
            if pain_type:
                parts.append(pain_type)
            return ' - '.join(parts) if parts else 'Pain logged'

        elif self.capture_type == 'intimacy':
            rating = data.get('rating')
            if rating:
                try:
                    rating = int(rating)
                    return '🍀 ' + '★' * rating
                except (ValueError, TypeError):
                    pass
            return '🍀'

        elif self.capture_type == 'cycle':
            event_type = data.get('event_type', '').replace('_', ' ').title()
            return event_type or 'Cycle event'

        return str(data)


class SharedPOV(models.Model):
    """
    A Point of View block shared with specific friends.

    Extracted from journal entries using {pov} @user1 @user2 content {/pov} syntax.
    Only tagged friends (who are actual friends) can see this content.
    """
    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name='shared_povs'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='authored_povs'
    )
    content = models.TextField(
        help_text="The POV content (markdown)"
    )
    content_hash = models.CharField(
        max_length=64,
        help_text="Hash to identify this POV block in the entry"
    )
    position_index = models.PositiveIntegerField(
        default=0,
        help_text="Order of this POV in the entry (0-indexed)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['entry', 'position_index']
        indexes = [
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['entry', 'position_index']),
        ]

    def __str__(self):
        return f"POV by {self.author.email} on {self.entry.entry_date}"

    @property
    def preview(self):
        """Return first 100 characters of content for previews."""
        if len(self.content) > 100:
            return self.content[:100] + '...'
        return self.content


class SharedPOVRecipient(models.Model):
    """
    Links a SharedPOV to a specific recipient.

    Tracks read status and notification delivery per recipient.
    """
    pov = models.ForeignKey(
        SharedPOV,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_povs'
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['pov', 'user']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"POV for {self.user.email}"


class POVReply(models.Model):
    """
    Reply to a SharedPOV.

    Only the author and tagged recipients can reply.
    """
    pov = models.ForeignKey(
        SharedPOV,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pov_replies'
    )
    content = models.TextField(max_length=2000)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['pov', 'created_at']),
        ]

    def __str__(self):
        return f"Reply by {self.author.email} on POV {self.pov.id}"


class GeocodedLocation(models.Model):
    """
    Cache for geocoded location names.

    Stores lat/lng coordinates for place names to avoid
    repeated API calls to the geocoding service.
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    geocoded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-geocoded_at']

    def __str__(self):
        if self.lat and self.lng:
            return f"{self.name} ({self.lat:.4f}, {self.lng:.4f})"
        return f"{self.name} (not geocoded)"

    @property
    def has_coordinates(self):
        return self.lat is not None and self.lng is not None


class PromptCategory(models.Model):
    """
    Categories of journal prompts users can subscribe to.

    Users can select multiple categories to receive varied prompts
    tailored to their needs (e.g., anxiety, gratitude, teens).
    """
    name = models.CharField(max_length=100)  # e.g., "Anxiety", "Gratitude"
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi-lightbulb')  # Bootstrap icon
    color = models.CharField(max_length=7, default='#7c3aed')  # Hex color for card
    image_url = models.URLField(
        blank=True,
        help_text="Background image URL for the category card"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default category shown to users who haven't selected any"
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Prompt Category'
        verbose_name_plural = 'Prompt Categories'

    def __str__(self):
        return self.name

    @property
    def prompt_count(self):
        return self.prompts.filter(is_active=True).count()


class Prompt(models.Model):
    """
    Individual prompts within a category.

    Each category has multiple prompts that rotate daily.
    """
    category = models.ForeignKey(
        PromptCategory,
        on_delete=models.CASCADE,
        related_name='prompts'
    )
    text = models.TextField()
    day_number = models.PositiveIntegerField(
        default=1,
        help_text="Used for sequential rotation within category"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'day_number']

    def __str__(self):
        return f"{self.category.name}: {self.text[:50]}..."

    @property
    def text_preview(self):
        """Return first 80 characters of prompt text."""
        if len(self.text) > 80:
            return self.text[:80] + '...'
        return self.text


class UserPromptPreference(models.Model):
    """
    User's selected prompt categories.

    Many-to-many through table allowing users to subscribe to
    multiple prompt categories.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='prompt_preferences'
    )
    category = models.ForeignKey(
        PromptCategory,
        on_delete=models.CASCADE,
        related_name='subscribers'
    )
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'category']
        ordering = ['selected_at']

    def __str__(self):
        return f"{self.user.email} → {self.category.name}"
