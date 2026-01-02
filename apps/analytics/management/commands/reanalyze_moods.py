"""
Management command to re-analyze mood for all entries.

Usage:
    python manage.py reanalyze_moods           # All entries
    python manage.py reanalyze_moods --user 1  # Specific user
    python manage.py reanalyze_moods --dry-run # Preview changes
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.journal.models import Entry
from apps.analytics.models import EntryAnalysis
from apps.analytics.services import get_sentiment_score, classify_mood


class Command(BaseCommand):
    help = 'Re-analyze mood for all entries using VADER sentiment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=int,
            help='User ID to re-analyze (default: all users)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving',
        )

    def handle(self, *args, **options):
        user_id = options.get('user')
        dry_run = options.get('dry_run')

        # Get entries with analysis
        queryset = EntryAnalysis.objects.select_related('entry', 'entry__user')

        if user_id:
            queryset = queryset.filter(entry__user_id=user_id)
            self.stdout.write(f"Re-analyzing entries for user {user_id}...")
        else:
            self.stdout.write("Re-analyzing entries for all users...")

        total = queryset.count()
        updated = 0
        changed = 0

        for analysis in queryset.iterator():
            entry = analysis.entry
            old_mood = analysis.detected_mood
            old_sentiment = analysis.sentiment_score

            # Re-calculate sentiment and mood
            content = entry.content
            if not content or content.startswith('gAAAAA'):
                # Skip encrypted entries without available key
                continue

            new_sentiment = get_sentiment_score(content)
            new_mood, confidence, _ = classify_mood(content, new_sentiment)

            updated += 1

            if old_mood != new_mood:
                changed += 1
                self.stdout.write(
                    f"  Entry {entry.id}: {old_mood} -> {new_mood} "
                    f"(sentiment: {old_sentiment:.2f} -> {new_sentiment:.2f})"
                )

                if not dry_run:
                    analysis.sentiment_score = new_sentiment
                    analysis.detected_mood = new_mood
                    analysis.mood_confidence = confidence
                    analysis.save(update_fields=['sentiment_score', 'detected_mood', 'mood_confidence'])

            if updated % 100 == 0:
                self.stdout.write(f"  Processed {updated}/{total}...")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN: Would update {changed}/{updated} entries"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nUpdated {changed}/{updated} entries"
            ))
