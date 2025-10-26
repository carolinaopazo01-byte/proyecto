from django.apps import AppConfig

class AtletaConfig(AppConfig):
    name = "applications.atleta"
    verbose_name = "Atleta"

    def ready(self):
        from . import signals  # noqa