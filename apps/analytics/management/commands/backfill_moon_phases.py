"""
Management command to backfill moon phase data for existing entries.

This command calculates and stores moon phase information for all entries
that have been analyzed but don't have moon phase data yet.

Usage:
    python manage.py backfill_moon_phases
    python manage.py backfill_moon_phases --user=user@example.com
    python manage.py backfill_moon_phases --dry-run
    python manage.py backfill_moon_phases --all  (include entries without analysis)
"""
import math
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from apps.journal.models import Entry
from apps.analytics.models import EntryAnalysis

# Moon phase calculation constants
MOON_PHASES = [
    'new_moon', 'waxing_crescent', 'first_quarter', 'waxing_gibbous',
    'full_moon', 'waning_gibbous', 'last_quarter', 'waning_crescent',
]
SYNODIC_MONTH = 29.53058867
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, 0)


def calculate_moon_phase(target_date):
    """Calculate moon phase for a given date."""
    # Convert to datetime at noon
    if not isinstance(target_date, datetime):
        target_dt = datetime(target_date.year, target_date.month, target_date.day, 12, 0, 0)
    else:
        target_dt = target_date

    # Calculate days since known new moon
    diff = target_dt - KNOWN_NEW_MOON
    days_since = diff.total_seconds() / 86400.0

    # Calculate position in lunar cycle (0 to 1)
    lunar_cycle = (days_since % SYNODIC_MONTH) / SYNODIC_MONTH

    # Calculate illumination
    illumination_decimal = (1 - math.cos(lunar_cycle * 2 * math.pi)) / 2
    illumination_percent = illumination_decimal * 100

    # Determine phase name
    phase_index = int(lunar_cycle * 8) % 8
    phase_name = MOON_PHASES[phase_index]

    return phase_name, round(illumination_percent, 1)


class Command(BaseCommand):
    help = 'Backfill moon phase data for existing entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Only process entries for a specific user (email)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all entries (creates analysis for entries without one)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )

    def handle(self, *args, **options):
        user_email = options.get('user')
        process_all = options.get('all')
        dry_run = options.get('dry_run')

        # Build queryset
        if process_all:
            # Get all entries
            entries = Entry.objects.all()
        else:
            # Only get entries that have been analyzed
            entries = Entry.objects.filter(is_analyzed=True)

        if user_email:
            try:
                user = User.objects.get(email=user_email)
                entries = entries.filter(user=user)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with email {user_email} not found"))
                return

        # Filter for entries without moon phase data
        entries_with_analysis = entries.filter(analysis__isnull=False)
        entries_without_moon = entries_with_analysis.filter(
            analysis__moon_phase=''
        ).select_related('analysis').order_by('entry_date')

        total = entries_without_moon.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✓ All analyzed entries already have moon phase data!"))
            return

        self.stdout.write(f"Found {total} entries without moon phase data")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            for entry in entries_without_moon[:20]:  # Show first 20 only
                phase, illumination = calculate_moon_phase(entry.entry_date)
                self.stdout.write(
                    f"  {entry.entry_date} - {entry.title or 'Untitled'} -> {phase} ({illumination:.1f}% illumination)"
                )
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        # Process entries
        updated = 0
        errors = []

        with transaction.atomic():
            for i, entry in enumerate(entries_without_moon, 1):
                try:
                    # Calculate moon phase for entry date
                    phase, illumination = calculate_moon_phase(entry.entry_date)

                    # Update the analysis
                    entry.analysis.moon_phase = phase
                    entry.analysis.moon_illumination = illumination / 100.0  # Store as 0.0 to 1.0
                    entry.analysis.save(update_fields=['moon_phase', 'moon_illumination'])

                    updated += 1

                    if i % 100 == 0:
                        self.stdout.write(f"  Processed {i}/{total} entries...")

                    if i <= 10 or i % 500 == 0:  # Show details for first 10 and every 500th
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  [{i}/{total}] {entry.entry_date} -> {phase} ({illumination:.1f}%)"
                            )
                        )

                except Exception as e:
                    errors.append((entry.id, str(e)))
                    self.stdout.write(
                        self.style.ERROR(f"  [{i}/{total}] Error processing entry {entry.id}: {e}")
                    )

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("MOON PHASE BACKFILL COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Entries updated: {updated}")

        if errors:
            self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
            for entry_id, error in errors[:10]:
                self.stdout.write(self.style.ERROR(f"  Entry {entry_id}: {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ No errors!"))

        self.stdout.write("")
        self.stdout.write("Moon phase correlations will now appear in your dashboard!")
