from django.apps import AppConfig

class PmulConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.pmul"          # <-- ruta del paquete del app
    verbose_name = "Profesional Multidisciplinario"
