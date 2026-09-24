from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

TESTING = os.environ.get("DJANGO_TESTING") == "1"
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

configured_secret = os.environ.get("DJANGO_SECRET_KEY")
if not configured_secret:
    if DEBUG or TESTING:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is disabled")
else:
    SECRET_KEY = configured_secret

if not DEBUG and SECRET_KEY == "dev-only-insecure-key":
    raise ImproperlyConfigured("The development SECRET_KEY cannot be used with DEBUG disabled")

configured_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS")
if configured_hosts is None and not DEBUG and not TESTING:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DEBUG is disabled")
ALLOWED_HOSTS = [
    host.strip()
    for host in (configured_hosts or "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "drf_spectacular",
    "django_filters",

    "billing",
    "users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if TESTING:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}}
else:
    postgres_values = {
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
    missing_postgres = [key for key in ("NAME", "USER", "PASSWORD") if not postgres_values[key]]
    if missing_postgres and not DEBUG:
        raise ImproperlyConfigured(
            "PostgreSQL settings are required when DEBUG is disabled: "
            + ", ".join(missing_postgres)
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": postgres_values["NAME"] or "billing_db",
            "USER": postgres_values["USER"] or "billing_user",
            "PASSWORD": postgres_values["PASSWORD"] or "billing_pass",
            "HOST": postgres_values["HOST"],
            "PORT": postgres_values["PORT"],
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Billing API",
    "DESCRIPTION": "Provider/Barrel/Invoice/InvoiceLine API",
    "VERSION": "1.0.0",
}
