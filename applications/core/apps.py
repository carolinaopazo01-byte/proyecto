from django.apps import AppConfig


from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications.core'

    def ready(self):
        # IMPORTA LAS SEÑALES
        from . import signals  # noqa
