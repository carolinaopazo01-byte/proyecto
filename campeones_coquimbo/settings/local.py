# campeones_coquimbo/settings/local.py
from .base import *
import os
from pathlib import Path

# === Desarrollo ===
DEBUG = True
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "admin123")
ALLOWED_HOSTS: list[str] = []

# === Base de datos (SQLite para dev) ===
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# === Seguridad (dev sin HTTPS) ===
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# === Auth / sesiones ===
# Usa solo UNA definición (evita duplicados).
LOGIN_URL = "usuarios:login_rut"
LOGIN_REDIRECT_URL = "/usuarios/panel/"
LOGOUT_REDIRECT_URL = "/"

AUTH_USER_MODEL = "usuarios.Usuario"
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# === Email (consola en dev) ===
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# === Static & Media (opcional en local: ya están en base.py)
# Si prefieres dejarlos explícitos en local también, mantenlos iguales a base.py.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
