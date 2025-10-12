from .base import *

DEBUG = True
ALLOWED_HOSTS = []

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

AUTH_USER_MODEL = "usuarios.Usuario"
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]
