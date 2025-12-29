"""
Management command to backfill streak badges for existing users.

Usage:
    python manage.py backfill_badges              # All users
    python manage.py backfill_badges --user=email # Specific user
    python manage.py backfill_badges --dry-run    # Show what would happen
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Backfill streak badges for existing users based on their entry history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Email of specific user to backfill (default: all users)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what badges would be awarded without actually awarding them',
        )

    def handle(self, *args, **options):
        from apps.journal.models import Entry
        from apps.accounts.models import UserBadge, STREAK_BADGES

        dry_run = options['dry_run']
        user_email = options.get('user')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made\n'))

        # Get users to process
        if user_email:
            users = User.objects.filter(email=user_email)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'User not found: {user_email}'))
                return
        else:
            users = User.objects.all()

        total_badges_awarded = 0

        for user in users:
            # Get all entry dates for this user
            entry_dates = set(
                Entry.objects.filter(user=user).values_list('entry_date', flat=True)
            )

            if not entry_dates:
                continue

            # Calculate longest streak (not just current streak)
            longest_streak = self.calculate_longest_streak(entry_dates)
            current_streak = self.calculate_current_streak(entry_dates)

            if longest_streak == 0:
                continue

            self.stdout.write(f'\n{user.email}:')
            self.stdout.write(f'  Total entries: {len(entry_dates)}')
            self.stdout.write(f'  Current streak: {current_streak} days')
            self.stdout.write(f'  Longest streak: {longest_streak} days')

            # Get existing badges for user
            existing_badges = set(
                UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
            )

            # Determine which badges should be awarded based on longest streak
            badges_to_award = []
            for badge in STREAK_BADGES:
                if badge['id'] not in existing_badges and longest_streak >= badge['days']:
                    badges_to_award.append(badge)

            if badges_to_award:
                self.stdout.write(self.style.SUCCESS(f'  Badges to award:'))
                for badge in badges_to_award:
                    self.stdout.write(f'    - {badge["name"]} ({badge["days"]} days) [{badge["tier"]}]')

                    if not dry_run:
                        UserBadge.objects.create(
                            user=user,
                            badge_id=badge['id'],
                            streak_count=longest_streak
                        )
                        total_badges_awarded += 1
            else:
                self.stdout.write(f'  No new badges to award (already has all earned badges)')

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Done! Awarded {total_badges_awarded} badges total.'))

    def calculate_longest_streak(self, entry_dates):
        """Calculate the longest consecutive streak from entry dates."""
        if not entry_dates:
            return 0

        sorted_dates = sorted(entry_dates)
        longest = 1
        current = 1

        for i in range(1, len(sorted_dates)):
            diff = (sorted_dates[i] - sorted_dates[i-1]).days
            if diff == 1:
                current += 1
                longest = max(longest, current)
            elif diff > 1:
                current = 1

        return longest

    def calculate_current_streak(self, entry_dates):
        """Calculate current consecutive streak ending today or yesterday."""
        if not entry_dates:
            return 0

        today = timezone.now().date()
        check_date = today

        # If no entry today, start from yesterday
        if check_date not in entry_dates:
            check_date = today - timedelta(days=1)

        streak = 0
        while check_date in entry_dates:
            streak += 1
            check_date -= timedelta(days=1)

        return streak
