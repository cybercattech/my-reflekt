from django.db import models
from django.contrib.auth.models import User
from apps.journal.models import Entry


class EntryAnalysis(models.Model):
    """
    NLP analysis results for a journal entry.

    Created asynchronously after an entry is saved.
    Stores sentiment, detected mood, keywords, and themes.
    """
    entry = models.OneToOneField(
        Entry,
        on_delete=models.CASCADE,
        related_name='analysis'
    )

    # Sentiment analysis
    sentiment_score = models.FloatField(
        help_text="Polarity score from -1.0 (negative) to 1.0 (positive)"
    )
    sentiment_label = models.CharField(
        max_length=20,
        help_text="positive, negative, or neutral"
    )

    # AI-detected mood (may differ from user-selected mood)
    detected_mood = models.CharField(max_length=20)
    mood_confidence = models.FloatField(
        default=0.5,
        help_text="Confidence score 0.0 to 1.0"
    )

    # Extracted data
    keywords = models.JSONField(
        default=list,
        help_text="Top keywords extracted from entry"
    )
    themes = models.JSONField(
        default=list,
        help_text="Detected themes (work, family, health, etc.)"
    )

    # Auto-generated summary
    summary = models.TextField(
        blank=True,
        help_text="AI-generated summary of the entry"
    )

    # Moon phase data
    moon_phase = models.CharField(
        max_length=20,
        blank=True,
        help_text="Moon phase name: new_moon, waxing_crescent, first_quarter, etc."
    )
    moon_illumination = models.FloatField(
        null=True,
        blank=True,
        help_text="Moon illumination 0.0 to 1.0"
    )

    # Weather data (captured at entry creation)
    weather_location = models.CharField(
        max_length=150,
        blank=True,
        help_text="City and country where weather was fetched from"
    )
    weather_condition = models.CharField(
        max_length=50,
        blank=True,
        help_text="Main weather condition: clear, clouds, rain, etc."
    )
    weather_description = models.CharField(
        max_length=100,
        blank=True,
        help_text="Detailed weather description"
    )
    temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="Temperature in Celsius"
    )
    humidity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Humidity percentage"
    )
    weather_icon = models.CharField(
        max_length=10,
        blank=True,
        help_text="OpenWeatherMap icon code"
    )

    # Horoscope data
    zodiac_sign = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's zodiac sign: aries, taurus, etc."
    )

    # Timestamp
    analyzed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entry Analysis'
        verbose_name_plural = 'Entry Analyses'

    def __str__(self):
        return f"Analysis for Entry {self.entry.id}"


class MonthlySnapshot(models.Model):
    """
    Aggregated monthly statistics for a user.

    Pre-computed for fast dashboard loading.
    Updated whenever entries in that month are analyzed.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='monthly_snapshots'
    )
    year = models.IntegerField()
    month = models.IntegerField()

    # Aggregates
    entry_count = models.IntegerField(default=0)
    total_words = models.IntegerField(default=0)
    avg_sentiment = models.FloatField(default=0.0)
    dominant_mood = models.CharField(max_length=20, blank=True)

    # Mood distribution
    mood_distribution = models.JSONField(
        default=dict,
        help_text='{"ecstatic": 2, "happy": 15, "neutral": 10, "sad": 3, "angry": 1}'
    )

    # Top themes this month
    top_themes = models.JSONField(default=list)

    # Highlights (entry IDs)
    best_day_id = models.IntegerField(null=True, blank=True)
    best_day_sentiment = models.FloatField(null=True, blank=True)
    worst_day_id = models.IntegerField(null=True, blank=True)
    worst_day_sentiment = models.FloatField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'year', 'month']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.user.email} - {self.year}/{self.month:02d}"

    @property
    def month_name(self):
        import calendar
        return calendar.month_name[self.month]


class YearlyReview(models.Model):
    """
    Annual summary and insights.

    The crown jewel - this is what users come back for.
    Generated on demand or scheduled for early January.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='yearly_reviews'
    )
    year = models.IntegerField()

    # Overall stats
    total_entries = models.IntegerField(default=0)
    total_words = models.IntegerField(default=0)
    avg_sentiment = models.FloatField(default=0.0)
    dominant_mood = models.CharField(max_length=20, blank=True)

    # Distribution
    mood_distribution = models.JSONField(
        default=dict,
        help_text="Full year mood breakdown"
    )

    # Monthly trend (12 data points)
    monthly_trend = models.JSONField(
        default=list,
        help_text="[{month: 1, sentiment: 0.12, mood: 'happy'}, ...]"
    )

    # Themes analysis
    top_themes = models.JSONField(
        default=list,
        help_text="Top themes for the year"
    )
    theme_sentiments = models.JSONField(
        default=dict,
        help_text="Sentiment score per theme"
    )
    theme_entry_counts = models.JSONField(
        default=dict,
        help_text="Number of entries per theme"
    )

    # Highlights and lowlights (list of entry summaries)
    highlights = models.JSONField(
        default=list,
        help_text="Top 10 best days with previews"
    )
    lowlights = models.JSONField(
        default=list,
        help_text="Top 10 challenging days with previews"
    )

    # AI-generated narrative summary
    narrative_summary = models.TextField(
        blank=True,
        help_text="AI-generated year-in-review narrative"
    )

    # Key insights (bullet points)
    insights = models.JSONField(
        default=list,
        help_text="Key observations about the year"
    )

    # Timestamps
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'year']
        ordering = ['-year']

    def __str__(self):
        return f"{self.user.email} - Year {self.year} Review"


class TrackedBook(models.Model):
    """
    Aggregates book captures into reading journeys.

    When user logs /book multiple times for the same book,
    this model tracks the full journey from start to finish.
    """
    STATUS_CHOICES = [
        ('want_to_read', 'Want to Read'),
        ('reading', 'Currently Reading'),
        ('finished', 'Finished'),
        ('abandoned', 'Abandoned'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tracked_books'
    )

    # Canonical book data
    title = models.CharField(max_length=300)
    normalized_title = models.CharField(max_length=300, db_index=True)
    author = models.CharField(max_length=200, blank=True)
    normalized_author = models.CharField(max_length=200, blank=True, db_index=True)

    # Reading status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='reading'
    )

    # Timeline
    started_date = models.DateField(null=True, blank=True)
    finished_date = models.DateField(null=True, blank=True)

    # Progress tracking
    current_page = models.IntegerField(default=0)
    total_pages = models.IntegerField(null=True, blank=True)

    # Rating (1-5 stars)
    rating = models.IntegerField(null=True, blank=True)

    # Link to all captures for this book
    captures = models.ManyToManyField(
        'journal.EntryCapture',
        related_name='tracked_book',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'normalized_title', 'normalized_author']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'finished_date']),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} by {self.author or 'Unknown'}"

    @property
    def progress_percentage(self):
        if self.total_pages and self.total_pages > 0:
            return min(100, int((self.current_page / self.total_pages) * 100))
        return 0

    @property
    def status_icon(self):
        icons = {
            'want_to_read': 'bi-bookmark',
            'reading': 'bi-book-half',
            'finished': 'bi-check-circle',
            'abandoned': 'bi-x-circle',
        }
        return icons.get(self.status, 'bi-book')

    @property
    def star_rating_display(self):
        if not self.rating:
            return ''
        return '★' * self.rating + '☆' * (5 - self.rating)


class TrackedPerson(models.Model):
    """
    Aggregates person mentions for social analytics.

    Groups mentions of the same person across entries using
    fuzzy name matching.
    """
    RELATIONSHIP_CHOICES = [
        ('partner', 'Partner'),
        ('family', 'Family'),
        ('friend', 'Friend'),
        ('colleague', 'Colleague'),
        ('acquaintance', 'Acquaintance'),
        ('other', 'Other'),
    ]

    SENTIMENT_CHOICES = [
        ('love', 'Love'),
        ('like', 'Like'),
        ('neutral', 'Neutral'),
        ('dislike', 'Dislike'),
        ('hate', 'Hate'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tracked_people'
    )

    # Canonical name
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, db_index=True)

    # Relationship type (user can categorize)
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        default='other'
    )

    # How user feels about this person
    sentiment = models.CharField(
        max_length=20,
        choices=SENTIMENT_CHOICES,
        default='neutral'
    )

    # Optional notes about this person
    notes = models.TextField(blank=True, default='')

    # Denormalized stats for performance
    mention_count = models.IntegerField(default=0)
    first_mention_date = models.DateField(null=True, blank=True)
    last_mention_date = models.DateField(null=True, blank=True)

    # Link to all captures mentioning this person
    captures = models.ManyToManyField(
        'journal.EntryCapture',
        related_name='tracked_person',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'normalized_name']
        ordering = ['-mention_count', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()})"

    @property
    def relationship_icon(self):
        icons = {
            'partner': 'bi-heart',
            'family': 'bi-house-heart',
            'friend': 'bi-people',
            'colleague': 'bi-briefcase',
            'acquaintance': 'bi-person',
            'other': 'bi-person-circle',
        }
        return icons.get(self.relationship, 'bi-person')

    def update_stats(self):
        """Recalculate denormalized stats from captures."""
        captures = self.captures.all().select_related('entry')
        self.mention_count = captures.count()

        if captures.exists():
            dates = [c.entry.entry_date for c in captures]
            self.first_mention_date = min(dates)
            self.last_mention_date = max(dates)
        else:
            self.first_mention_date = None
            self.last_mention_date = None

        self.save()


class CaptureSnapshot(models.Model):
    """
    Pre-computed capture aggregates by type and period.

    Similar to MonthlySnapshot but for captures.
    Enables fast dashboard loading.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='capture_snapshots'
    )
    year = models.IntegerField()
    month = models.IntegerField(null=True, blank=True)  # null = yearly aggregate
    capture_type = models.CharField(max_length=20)

    # Aggregates
    count = models.IntegerField(default=0)

    # Type-specific data (flexible schema)
    # workout: {"total_duration": 1200, "avg_duration": 45, "by_type": {"run": 10}}
    # watched: {"by_rating": {5: 3, 4: 7}, "by_type": {"movie": 5, "show": 10}}
    # book: {"finished": 12, "reading": 2, "avg_rating": 4.2}
    data = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'year', 'month', 'capture_type']
        indexes = [
            models.Index(fields=['user', 'capture_type', 'year']),
        ]

    def __str__(self):
        period = f"{self.year}/{self.month:02d}" if self.month else str(self.year)
        return f"{self.user.email} - {self.capture_type} - {period}"
