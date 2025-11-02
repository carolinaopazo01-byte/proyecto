# campeones_coquimbo/settings/base.py
from pathlib import Path

# === Rutas principales
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === Clave secreta
# No hardcodees en producción: léela desde el entorno en production.py
SECRET_KEY = "admin123"  # ← solo para desarrollo; en prod úsala desde variables de entorno

# === Django / Apps instaladas
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Terceros
    "django_filters",
    "django.contrib.humanize",

    # Tus apps
    "applications.usuarios",
    "applications.atleta",
    "applications.evaluaciones",
    "applications.pmul.apps.PmulConfig",
    "applications.profesor",
    "applications.core.apps.CoreConfig",
]

# === Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise debe ir inmediatamente después de SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# === URLs / WSGI
ROOT_URLCONF = "campeones_coquimbo.urls"
WSGI_APPLICATION = "campeones_coquimbo.wsgi.application"

# === Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # carpeta global de templates
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

# === Autenticación
AUTH_USER_MODEL = "usuarios.Usuario"  # app_label.Model
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# === Validadores de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# === Internacionalización
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# === Archivos estáticos / media
# STATICFILES_DIRS apunta a tus fuentes estáticas (ej. /static del proyecto).
# STATIC_ROOT es donde collectstatic juntará todo para servir en prod.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise: sirve estáticos comprimidos y con hash en producción
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media (subidas de usuarios)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# === Seguridad (ajusta en cada entorno)
# En desarrollo (local.py) normalmente:
#   DEBUG = True
#   CSRF_COOKIE_SECURE = False
#   SESSION_COOKIE_SECURE = False
# En producción (production.py) normalmente:
#   DEBUG = False
#   CSRF_COOKIE_SECURE = True
#   SESSION_COOKIE_SECURE = True
#   SECURE_SSL_REDIRECT = True
#   ALLOWED_HOSTS = ["tu-app.onrender.com"]
#   CSRF_TRUSTED_ORIGINS = ["https://tu-app.onrender.com"]

# === Otros
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Base de datos
# Define la DB por entorno:
# - En local.py: SQLite (ya lo tienes)
# - En production.py: Postgres (por DATABASE_URL)
# Si quieres, puedes dejar aquí un stub y sobreescribir por entorno:
# DATABASES = {}
