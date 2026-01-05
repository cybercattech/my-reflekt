"""
Management command to analyze unanalyzed journal entries.

Usage:
    python manage.py analyze_entries                    # Analyze all unanalyzed
    python manage.py analyze_entries --user=username    # Analyze for specific user
    python manage.py analyze_entries --limit=100        # Analyze only 100 entries
    python manage.py analyze_entries --force            # Re-analyze all entries
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.journal.models import Entry
from apps.journal.signals import run_sync_analysis

User = get_user_model()


class Command(BaseCommand):
    help = 'Analyze unanalyzed journal entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to analyze entries for (optional)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of entries to analyze (0 for unlimited)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-analyze all entries, even already analyzed ones',
        )

    def handle(self, *args, **options):
        username = options.get('user')
        limit = options.get('limit')
        force = options.get('force')

        # Build queryset
        entries = Entry.objects.all()

        if username:
            try:
                user = User.objects.get(username=username)
                entries = entries.filter(user=user)
                self.stdout.write(f"Filtering entries for user: {username}")
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User '{username}' not found"))
                return

        if not force:
            entries = entries.filter(is_analyzed=False)

        # Order by date (oldest first)
        entries = entries.order_by('entry_date')

        if limit > 0:
            entries = entries[:limit]

        total = entries.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No entries to analyze!"))
            return

        self.stdout.write(f"Found {total} entries to analyze...")

        analyzed = 0
        errors = 0

        for entry in entries:
            try:
                run_sync_analysis(entry)
                analyzed += 1
                if analyzed % 10 == 0:
                    self.stdout.write(f"  Analyzed {analyzed}/{total}...")
            except Exception as e:
                errors += 1
                self.stderr.write(
                    self.style.WARNING(f"  Error analyzing entry {entry.id}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Analyzed {analyzed} entries, {errors} errors.")
        )
        self.stdout.write("Monthly snapshots updated automatically.")
