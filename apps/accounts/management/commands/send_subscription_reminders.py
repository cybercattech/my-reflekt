"""
Management command to send subscription reminder emails.

Run daily via cron:
    python manage.py send_subscription_reminders

This command sends:
1. Trial ending reminders (2 days before trial ends)
2. Payment reminders (1 day before billing)
"""
import stripe
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import Profile
from apps.accounts.subscription_emails import (
    send_trial_ending_reminder_email,
    send_payment_reminder_email,
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send subscription reminder emails (trial ending, payment due)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending emails',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No emails will be sent'))

        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get all premium users with active subscriptions
        premium_profiles = Profile.objects.filter(
            subscription_tier='premium',
            stripe_subscription_id__isnull=False
        ).exclude(stripe_subscription_id='').select_related('user')

        trial_reminders_sent = 0
        payment_reminders_sent = 0
        errors = 0

        for profile in premium_profiles:
            try:
                # Get subscription from Stripe
                subscription = stripe.Subscription.retrieve(profile.stripe_subscription_id)

                # Check for trial ending (send reminder 2 days before)
                if subscription.status == 'trialing' and subscription.trial_end:
                    trial_end = datetime.fromtimestamp(subscription.trial_end)
                    days_until_trial_end = (trial_end.date() - datetime.now().date()).days

                    if days_until_trial_end == 2:
                        if dry_run:
                            self.stdout.write(
                                f'Would send trial ending reminder to {profile.user.email} '
                                f'(trial ends in {days_until_trial_end} days)'
                            )
                        else:
                            send_trial_ending_reminder_email(
                                profile.user,
                                days_until_trial_end,
                                trial_end
                            )
                            logger.info(f'Sent trial ending reminder to {profile.user.email}')
                        trial_reminders_sent += 1

                # Check for payment due (send reminder 1 day before for active subscriptions)
                elif subscription.status == 'active' and subscription.current_period_end:
                    billing_date = datetime.fromtimestamp(subscription.current_period_end)
                    days_until_billing = (billing_date.date() - datetime.now().date()).days

                    if days_until_billing == 1:
                        # Get the plan amount
                        amount = subscription['items']['data'][0]['price']['unit_amount'] / 100
                        plan_name = self._get_plan_name(profile.subscription_plan)

                        if dry_run:
                            self.stdout.write(
                                f'Would send payment reminder to {profile.user.email} '
                                f'(${amount} due tomorrow for {plan_name})'
                            )
                        else:
                            send_payment_reminder_email(
                                profile.user,
                                billing_date,
                                amount,
                                plan_name
                            )
                            logger.info(f'Sent payment reminder to {profile.user.email}')
                        payment_reminders_sent += 1

            except stripe.error.StripeError as e:
                errors += 1
                logger.error(f'Stripe error for {profile.user.email}: {e}')
                self.stdout.write(
                    self.style.ERROR(f'Stripe error for {profile.user.email}: {e}')
                )
            except Exception as e:
                errors += 1
                logger.error(f'Error processing {profile.user.email}: {e}')
                self.stdout.write(
                    self.style.ERROR(f'Error processing {profile.user.email}: {e}')
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Trial ending reminders: {trial_reminders_sent}'))
        self.stdout.write(self.style.SUCCESS(f'Payment reminders: {payment_reminders_sent}'))
        if errors:
            self.stdout.write(self.style.ERROR(f'Errors: {errors}'))
        self.stdout.write(self.style.SUCCESS('Done!'))

    def _get_plan_name(self, subscription_plan):
        """Convert subscription_plan code to readable name."""
        plan_names = {
            'individual_monthly': 'Individual Monthly',
            'individual_yearly': 'Individual Yearly',
            'family_monthly': 'Family Monthly',
            'family_yearly': 'Family Yearly',
        }
        return plan_names.get(subscription_plan, 'Premium')
