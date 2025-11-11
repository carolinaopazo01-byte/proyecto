from django.contrib import admin
from .models import AsistenciaProfesor

@admin.register(AsistenciaProfesor)
class AsistenciaProfesorAdmin(admin.ModelAdmin):

    list_display = ("usuario", "sede", "fecha", "hora", "tipo")
    list_filter = ("sede", "tipo", "fecha")
    ordering = ("-fecha", "-hora")
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
    )
