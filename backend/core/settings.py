"""
Django settings for core project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-((p#dw&!u17r($a=pu1217^-+cmctvs7#=wu)&!p_0r1lbl$^x'

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'fb-page-create.onrender.com', '.onrender.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'pages',
    'automation',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'staticfiles' / 'frontend'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# SQLite for Django admin/auth (keep for simplicity)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'staticfiles' / 'frontend' / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings for React frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://fb-page-create.onrender.com",
]
CORS_ALLOW_ALL_ORIGINS = not DEBUG  # Allow all in production (same origin anyway)

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}

# ===========================================
# Celery Configuration (Redis as broker)
# ===========================================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max per task

# ===========================================
# MongoDB Configuration
# ===========================================
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'facebook_pages')

# ===========================================
# Selenium Configuration
# ===========================================
# HEADLESS = False means browser is VISIBLE so you can see the automation
SELENIUM_HEADLESS = os.getenv('SELENIUM_HEADLESS', 'False') == 'True'
SELENIUM_TIMEOUT = int(os.getenv('SELENIUM_TIMEOUT', '30'))
CHROMEDRIVER_PATH = os.getenv('CHROMEDRIVER_PATH', None)  # None = auto-detect
SELENIUM_TEST_MODE = os.getenv('SELENIUM_TEST_MODE', 'False') == 'True'

# ===========================================
# Hardcoded Creator Profile (Logged-in Profile)
# This profile is used to log into Facebook and create pages
# ===========================================
CREATOR_PROFILE_EMAIL = os.getenv('CREATOR_PROFILE_EMAIL', 'kritikaverma290902@gmail.com')
CREATOR_PROFILE_PASSWORD = os.getenv('CREATOR_PROFILE_PASSWORD', 'kritika@2909')

# ===========================================
# Multiple Facebook Accounts (for rotation to avoid rate limits)
# Format: email:password pairs
# ===========================================
FACEBOOK_ACCOUNTS = [
    # Primary account
    {
        'email': os.getenv('FB_ACCOUNT_1_EMAIL', 'kritikaverma290902@gmail.com'),
        'password': os.getenv('FB_ACCOUNT_1_PASSWORD', 'kritika@2909'),
        'active': True,
    },
    # Backup account (old one)
    {
        'email': os.getenv('FB_ACCOUNT_2_EMAIL', 'avinamoore@outlook.com'),
        'password': os.getenv('FB_ACCOUNT_2_PASSWORD', 'Aman5065'),
        'active': False,  # Set to True to enable
    },
]

# ===========================================
# Multi-Profile Rotation Settings
# Used to rotate between profiles to avoid rate limits
# ===========================================
# Pages to create per profile before rotating (default: 3)
PAGES_PER_PROFILE = int(os.getenv('PAGES_PER_PROFILE', '3'))

# List of creator profiles for rotation
# Format: [{'email': 'x@x.com', 'password': 'xxx', 'name': 'Profile 1'}, ...]
# If empty, falls back to CREATOR_PROFILE_EMAIL/PASSWORD
CREATOR_PROFILES = [
    {
        'email': os.getenv('CREATOR_PROFILE_1_EMAIL', os.getenv('CREATOR_PROFILE_EMAIL', 'kritikaverma290902@gmail.com')),
        'password': os.getenv('CREATOR_PROFILE_1_PASSWORD', os.getenv('CREATOR_PROFILE_PASSWORD', 'kritika@2909')),
        'name': 'Profile 1 (Primary)',
        'pages_per_session': PAGES_PER_PROFILE,
    },
    # Add more profiles here for rotation:
    # {
    #     'email': os.getenv('CREATOR_PROFILE_2_EMAIL', ''),
    #     'password': os.getenv('CREATOR_PROFILE_2_PASSWORD', ''),
    #     'name': 'Profile 2',
    #     'pages_per_session': PAGES_PER_PROFILE,
    # },
]

# Filter out profiles with empty credentials
CREATOR_PROFILES = [p for p in CREATOR_PROFILES if p.get('email') and p.get('password')]

# ===========================================
# Page Creation Settings (No Rate Limits)
# ===========================================
# No delays between page creations - natural flow
PAGE_CREATION_MIN_DELAY = int(os.getenv('PAGE_CREATION_MIN_DELAY', '0'))  # No delay
PAGE_CREATION_MAX_DELAY = int(os.getenv('PAGE_CREATION_MAX_DELAY', '0'))  # No delay

# No session limits
MAX_PAGES_PER_SESSION = int(os.getenv('MAX_PAGES_PER_SESSION', '100'))  # No practical limit

# No breaks needed
SESSION_BREAK_DURATION = int(os.getenv('SESSION_BREAK_DURATION', '0'))  # No break

# Proxy settings (optional - for IP rotation)
# Format: "http://user:pass@host:port" or "http://host:port"
PROXY_URL = os.getenv('PROXY_URL', '')  # Empty = no proxy

# Cookie persistence path (to avoid re-login)
COOKIES_FILE_PATH = os.getenv('COOKIES_FILE_PATH', str(BASE_DIR / 'facebook_cookies.json'))
