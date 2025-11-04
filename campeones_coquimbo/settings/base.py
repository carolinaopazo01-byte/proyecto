# campeones_coquimbo/settings/base.py
from pathlib import Path

# === Rutas principales
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === Clave secreta
# En producción se toma desde DJANGO_SECRET_KEY (production.py)
SECRET_KEY = "admin123"

# === Apps instaladas
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

    # Apps del proyecto
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
        "DIRS": [BASE_DIR / "templates"],
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

# === Usuario y autenticación
AUTH_USER_MODEL = "usuarios.Usuario"
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Redirecciones de auth (globales)
LOGIN_URL = "usuarios:login_rut"
LOGIN_REDIRECT_URL = "/usuarios/panel/"
LOGOUT_REDIRECT_URL = "/"

# === Validadores de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# === I18N / TZ
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# === Archivos estáticos y media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"          # destino de collectstatic
STATICFILES_DIRS = [BASE_DIR / "static"]        # fuentes estáticas del proyecto

# WhiteNoise: estáticos comprimidos con hash
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# === Otros
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Base de datos
# Se define por entorno:
# - local.py → SQLite
# - production.py → DATABASE_URL (Postgres) o fallback a SQLite
# DATABASES = {}  # intencionalmente definido en cada settings de entorno
