# campeones_coquimbo/settings/production.py
from .base import *
import os

# --- Básicos ---
DEBUG = False
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")

# Host proporcionado por Render
host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
ALLOWED_HOSTS = [host] if host else []
CSRF_TRUSTED_ORIGINS = [f"https://{host}"] if host else []

# Render detrás de proxy/CDN
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# --- Seguridad ---
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = True

# --- WhiteNoise (estáticos) ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Base de datos: Postgres si hay DATABASE_URL; si no, SQLite ---
db_url = os.getenv("DATABASE_URL")
if db_url:
    try:
        import dj_database_url
        DATABASES = {
            "default": dj_database_url.config(
                default=db_url,
                conn_max_age=600,
                ssl_require=True,
            )
        }
    except Exception:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Logging a consola (para ver errores en Render Runtime) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": True},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
