from django.apps import AppConfig

class AtletaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.atleta"

    def ready(self):
        from . import signals  # noqa
