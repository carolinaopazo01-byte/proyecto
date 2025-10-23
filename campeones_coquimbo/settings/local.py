from .base import *

DEBUG = True
SECRET_KEY = 'admin123'
ALLOWED_HOSTS = []

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
DEBUG = True


EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
LOGIN_URL = "/usuarios/login/"
LOGIN_REDIRECT_URL = "/usuarios/panel/"

AUTH_USER_MODEL = "usuarios.Usuario"
AUTHENTICATION_BACKENDS = [
    "applications.usuarios.auth_backends.RutBackend",
    "django.contrib.auth.backends.ModelBackend",
]
