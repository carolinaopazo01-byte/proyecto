# campeones_coquimbo/settings/local.py
from .base import *
import os
from pathlib import Path

DEBUG = True
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "admin123")
ALLOWED_HOSTS = []  # en dev está ok vacío

# === Base de datos (Render Postgres) ===
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "campeones_db",
        "USER": "campeones_db_user",
        "PASSWORD": "fWeRmxmuEIw4wwntYr6oOrON4LOmcgSX",
        "HOST": "dpg-d46h2pre5dus73b6pl6g-a.oregon-postgres.render.com",
        "PORT": "5432",
        "OPTIONS": {
            "sslmode": "require",  # <-- NECESARIO para Render
        },
    }
}

# === Regionalización
TIME_ZONE = "America/Santiago"
LANGUAGE_CODE = "es-cl"
USE_TZ = True

# === Seguridad
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True


LOGIN_URL = "usuarios:login_rut"
LOGIN_REDIRECT_URL = "/usuarios/panel/"
LOGOUT_REDIRECT_URL = "/"

AUTH_USER_MODEL = "usuarios.Usuario"
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@cpc.local"  # <-- para que el mail tenga remitente claro


STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
