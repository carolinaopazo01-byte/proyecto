# applications/core/admin.py
from django.contrib import admin
from .models import (
    Sede, Deporte, SedeDeporte, Evento,
    Comunicado, Curso, Planificacion
)

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "capacidad")
    search_fields = ("nombre", "direccion")

@admin.register(Deporte)
class DeporteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria")
    search_fields = ("nombre",)

@admin.register(SedeDeporte)
class SedeDeporteAdmin(admin.ModelAdmin):
    list_display = ("sede", "deporte", "activo", "cupos_max", "fecha_inicio")
    list_filter = ("sede", "deporte", "activo")

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha", "lugar", "tipo")
    list_filter = ("fecha", "tipo")
    search_fields = ("nombre", "lugar", "descripcion")

@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "creado")
    search_fields = ("titulo", "cuerpo")
    list_filter = ("creado",)

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "programa", "disciplina", "profesor", "sede", "cupos", "publicado")
    list_filter = ("programa", "disciplina", "sede", "publicado")
    search_fields = ("nombre", "profesor__rut", "profesor__username")

@admin.register(Planificacion)
class PlanificacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nivel_dificultad", "duracion", "creado", "creado_por")
    list_filter = ("nivel_dificultad",)
    search_fields = ("nombre", "contenido", "metodologia")
