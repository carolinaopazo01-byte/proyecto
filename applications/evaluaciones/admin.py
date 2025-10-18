# applications/evaluaciones/admin.py
from django.contrib import admin
from .models import Material, Evaluacion, Cita

# OJO: NO registrar Planificacion aquí (ya se registra en core.admin).

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("id",)     # usa solo campos seguros
    search_fields = ()

@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ()

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("id",)
    list_filter = ()
