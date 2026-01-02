"""
Development settings for Reflekt.
"""
from .base import *
import os
import certifi

# Fix SSL certificate verification for Python 3.13 on macOS
os.environ['SSL_CERT_FILE'] = certifi.where()

DEBUG = True

# Use SQLite for development if no DATABASE_URL is set
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR}/db.sqlite3'),
}

# Debug toolbar
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
INTERNAL_IPS = ['127.0.0.1']

# Debug toolbar configuration - hide the toolbar panel
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: False,  # Disable toolbar display
}

# Email - use SendGrid in development too (so we can test verification)
# Load from environment variables (set in .env file)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.sendgrid.net')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='apikey')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='info@myreflekt.net')

# Django 5.x storage configuration for development
# Override base.py to use simpler static files storage (no manifest)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
