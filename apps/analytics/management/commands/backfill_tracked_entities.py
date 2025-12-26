"""
Management command to backfill TrackedBook and TrackedPerson from existing captures.

Run this once after deploying the capture tracking feature to process
all existing EntryCapture records.

Usage:
    python manage.py backfill_tracked_entities
    python manage.py backfill_tracked_entities --user=user@example.com
    python manage.py backfill_tracked_entities --type=book
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.journal.models import EntryCapture
from apps.analytics.services import (
    get_or_create_tracked_book,
    get_or_create_tracked_person,
)


class Command(BaseCommand):
    help = 'Backfill TrackedBook and TrackedPerson from existing captures'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Only process captures for a specific user (email)',
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['book', 'person', 'all'],
            default='all',
            help='Type of captures to process (default: all)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )

    def handle(self, *args, **options):
        user_email = options.get('user')
        capture_type = options.get('type')
        dry_run = options.get('dry_run')

        # Build queryset
        captures = EntryCapture.objects.select_related('entry', 'entry__user')

        if user_email:
            captures = captures.filter(entry__user__email=user_email)

        if capture_type == 'book':
            captures = captures.filter(capture_type='book')
        elif capture_type == 'person':
            captures = captures.filter(capture_type='person')
        else:
            captures = captures.filter(capture_type__in=['book', 'person'])

        captures = captures.order_by('entry__entry_date')

        total = captures.count()
        self.stdout.write(f"Found {total} captures to process")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            for capture in captures[:20]:  # Show first 20 only
                self.stdout.write(
                    f"  [{capture.capture_type}] {capture.data.get('title') or capture.data.get('name')} "
                    f"(user: {capture.entry.user.email}, date: {capture.entry.entry_date})"
                )
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        # Process captures
        books_created = 0
        books_linked = 0
        people_created = 0
        people_linked = 0
        errors = []

        for i, capture in enumerate(captures, 1):
            try:
                user = capture.entry.user

                if capture.capture_type == 'book':
                    # Check if already linked
                    if capture.tracked_book.exists():
                        self.stdout.write(f"  [{i}/{total}] Book already linked: {capture.data.get('title')}")
                        continue

                    with transaction.atomic():
                        book = get_or_create_tracked_book(user, capture)
                        if book:
                            if book.captures.count() == 1:
                                books_created += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"  [{i}/{total}] Created book: {book.title}")
                                )
                            else:
                                books_linked += 1
                                self.stdout.write(
                                    f"  [{i}/{total}] Linked to existing book: {book.title}"
                                )

                elif capture.capture_type == 'person':
                    # Check if already linked
                    if capture.tracked_person.exists():
                        self.stdout.write(f"  [{i}/{total}] Person already linked: {capture.data.get('name')}")
                        continue

                    with transaction.atomic():
                        person = get_or_create_tracked_person(user, capture)
                        if person:
                            if person.captures.count() == 1:
                                people_created += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"  [{i}/{total}] Created person: {person.name}")
                                )
                            else:
                                people_linked += 1
                                self.stdout.write(
                                    f"  [{i}/{total}] Linked to existing person: {person.name}"
                                )

            except Exception as e:
                errors.append((capture.id, str(e)))
                self.stdout.write(
                    self.style.ERROR(f"  [{i}/{total}] Error processing capture {capture.id}: {e}")
                )

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("BACKFILL COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Books created:  {books_created}")
        self.stdout.write(f"Books linked:   {books_linked}")
        self.stdout.write(f"People created: {people_created}")
        self.stdout.write(f"People linked:  {people_linked}")

        if errors:
            self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
            for capture_id, error in errors[:10]:
                self.stdout.write(self.style.ERROR(f"  Capture {capture_id}: {error}"))
