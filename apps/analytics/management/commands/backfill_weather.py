"""
Management command to backfill weather data for existing entries.

This command fetches weather data for all analyzed entries that don't have it yet.

Usage:
    python manage.py backfill_weather
    python manage.py backfill_weather --user=user@example.com
    python manage.py backfill_weather --city="Boston" --country=US
    python manage.py backfill_weather --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from apps.journal.models import Entry
from apps.analytics.models import EntryAnalysis


class Command(BaseCommand):
    help = 'Backfill weather data for existing entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Only process entries for a specific user (email)',
        )
        parser.add_argument(
            '--city',
            type=str,
            help='Override city for weather lookup',
        )
        parser.add_argument(
            '--country',
            type=str,
            default='US',
            help='Country code for weather lookup (default: US)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of entries to process',
        )

    def handle(self, *args, **options):
        # Import weather module directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "weather_module",
            "/Users/sfetter/Documents/CyberCat/Sandbox/reflekt/apps/analytics/services/weather.py"
        )
        weather_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(weather_module)
        get_weather_data = weather_module.get_weather_data

        user_email = options.get('user')
        override_city = options.get('city')
        override_country = options.get('country')
        dry_run = options.get('dry_run')
        limit = options.get('limit')

        # Build queryset - entries that are analyzed but don't have weather
        entries_without_weather = Entry.objects.filter(
            is_analyzed=True,
            analysis__weather_location=''
        ).select_related('user__profile', 'analysis')

        if user_email:
            try:
                user = User.objects.get(email=user_email)
                entries_without_weather = entries_without_weather.filter(user=user)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with email {user_email} not found"))
                return

        if limit:
            entries_without_weather = entries_without_weather[:limit]

        total = entries_without_weather.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✓ All analyzed entries already have weather data!"))
            return

        self.stdout.write(f"Found {total} entries without weather data")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            for entry in entries_without_weather[:20]:  # Show first 20 only
                city = override_city or entry.city or (entry.user.profile.city if hasattr(entry.user, 'profile') else '')
                country = override_country or entry.country_code or (entry.user.profile.country_code if hasattr(entry.user, 'profile') else 'US')
                self.stdout.write(
                    f"  {entry.entry_date} - {entry.title or 'Untitled'} -> Would fetch weather for {city}, {country}"
                )
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        # Process entries
        updated = 0
        skipped = 0
        errors = []

        for i, entry in enumerate(entries_without_weather, 1):
            try:
                # Determine location
                if override_city:
                    city = override_city
                    country_code = override_country
                else:
                    # Use entry location if available, otherwise profile location
                    city = entry.city
                    country_code = entry.country_code

                    if not city and hasattr(entry.user, 'profile'):
                        city = entry.user.profile.city
                        country_code = entry.user.profile.country_code or 'US'

                if not city:
                    skipped += 1
                    if i <= 10:
                        self.stdout.write(f"  [{i}/{total}] Skipped (no location): {entry.entry_date}")
                    continue

                # Fetch weather
                weather_data = get_weather_data(city, country_code)

                if not weather_data:
                    skipped += 1
                    if i <= 10:
                        self.stdout.write(f"  [{i}/{total}] Skipped (no weather data): {entry.entry_date}")
                    continue

                # Update analysis
                entry.analysis.weather_location = f"{city}, {country_code}"
                entry.analysis.weather_condition = weather_data.get('condition', '')
                entry.analysis.weather_description = weather_data.get('description', '')
                entry.analysis.temperature = weather_data.get('temperature')
                entry.analysis.humidity = weather_data.get('humidity')
                entry.analysis.weather_icon = weather_data.get('icon_code', '')
                entry.analysis.save(update_fields=[
                    'weather_location',
                    'weather_condition',
                    'weather_description',
                    'temperature',
                    'humidity',
                    'weather_icon'
                ])

                updated += 1

                if i % 100 == 0:
                    self.stdout.write(f"  Processed {i}/{total} entries...")

                if i <= 10 or i % 500 == 0:  # Show details for first 10 and every 500th
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{i}/{total}] {entry.entry_date} -> {weather_data.get('condition')} in {city}"
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
        self.stdout.write(self.style.SUCCESS("WEATHER BACKFILL COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Entries updated: {updated}")
        self.stdout.write(f"Entries skipped: {skipped}")

        if errors:
            self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
            for entry_id, error in errors[:10]:
                self.stdout.write(self.style.ERROR(f"  Entry {entry_id}: {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ No errors!"))

        self.stdout.write("")
        self.stdout.write("Weather data will now appear in your entries!")
