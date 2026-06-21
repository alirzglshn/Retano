# config/settings/development.py
"""
Development settings — extends base.py.
Use: DJANGO_SETTINGS_MODULE=config.settings.development
"""

from .base import *  # noqa: F401, F403



# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DEV MUST NOT REQUIRE AN ACUTALL KAVENEGAR KEY
# ─────────────────────────────────────────────────────────────────────────────
OTP_FAKE_MODE = True 



# ─────────────────────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────────────────────

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
]

# ─────────────────────────────────────────────────────────────────────────────
# Security — relaxed for local development
# ─────────────────────────────────────────────────────────────────────────────

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow all origins locally
# ─────────────────────────────────────────────────────────────────────────────

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ─────────────────────────────────────────────────────────────────────────────
# DRF — add BrowsableAPI renderer in development only
# ─────────────────────────────────────────────────────────────────────────────

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# ─────────────────────────────────────────────────────────────────────────────
# Email — log to console instead of sending real emails
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ─────────────────────────────────────────────────────────────────────────────
# Logging — verbose SQL and debug info
# ─────────────────────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",  # logs all SQL queries — disable if noisy
            "propagate": False,
        },
        "retano": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Database SSL — disable for local dev (local Postgres has no SSL)
# ─────────────────────────────────────────────────────────────────────────────

DATABASES["default"]["OPTIONS"] = {"sslmode": "disable"}  # noqa: F405
