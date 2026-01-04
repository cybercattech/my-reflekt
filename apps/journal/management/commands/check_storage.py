"""
Management command to check storage configuration and S3 connectivity.

Usage:
    python manage.py check_storage
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
import os


class Command(BaseCommand):
    help = 'Check storage configuration and S3 connectivity'

    def handle(self, *args, **options):
        self.stdout.write("\n=== Storage Configuration Check ===\n")

        # Check which storage backend is configured
        storages = getattr(settings, 'STORAGES', {})
        default_backend = storages.get('default', {}).get('BACKEND', 'Not configured')

        self.stdout.write(f"Default storage backend: {default_backend}")

        if 'S3' in default_backend or 's3' in default_backend:
            self.stdout.write(self.style.SUCCESS("  -> S3 storage is configured"))
        elif 'FileSystem' in default_backend:
            self.stdout.write(self.style.WARNING("  -> Local FileSystem storage (files will be lost on deploy!)"))

        # Check AWS environment variables
        self.stdout.write("\n--- AWS Environment Variables ---")

        aws_vars = {
            'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID', ''),
            'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
            'AWS_STORAGE_BUCKET_NAME': os.environ.get('AWS_STORAGE_BUCKET_NAME', ''),
            'AWS_S3_REGION_NAME': os.environ.get('AWS_S3_REGION_NAME', 'us-east-1'),
        }

        all_set = True
        for var, value in aws_vars.items():
            if value:
                # Mask sensitive values
                if 'SECRET' in var or 'KEY' in var:
                    display = value[:4] + '****' + value[-4:] if len(value) > 8 else '****'
                else:
                    display = value
                self.stdout.write(f"  {var}: {display}")
            else:
                self.stdout.write(self.style.ERROR(f"  {var}: NOT SET"))
                if var != 'AWS_S3_REGION_NAME':
                    all_set = False

        # Check settings values
        self.stdout.write("\n--- Django Settings Values ---")
        self.stdout.write(f"  AWS_ACCESS_KEY_ID: {'Set' if getattr(settings, 'AWS_ACCESS_KEY_ID', '') else 'NOT SET'}")
        self.stdout.write(f"  AWS_STORAGE_BUCKET_NAME: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
        self.stdout.write(f"  AWS_S3_REGION_NAME: {getattr(settings, 'AWS_S3_REGION_NAME', 'NOT SET')}")

        # Test S3 connectivity if configured
        if 'S3' in default_backend or 's3' in default_backend:
            self.stdout.write("\n--- S3 Connectivity Test ---")
            try:
                # Try to list a directory (should not raise error)
                dirs, files = default_storage.listdir('')
                self.stdout.write(self.style.SUCCESS(f"  Successfully connected to S3"))
                self.stdout.write(f"  Found {len(dirs)} directories and {len(files)} files in root")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Failed to connect to S3: {e}"))

        # Summary
        self.stdout.write("\n--- Summary ---")
        if 'S3' in default_backend or 's3' in default_backend:
            self.stdout.write(self.style.SUCCESS("S3 is properly configured for media storage."))
        else:
            self.stdout.write(self.style.WARNING(
                "S3 is NOT configured. Files are stored locally and will be lost on deploy.\n"
                "To fix: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_STORAGE_BUCKET_NAME\n"
                "in your production environment variables."
            ))

        self.stdout.write("")
