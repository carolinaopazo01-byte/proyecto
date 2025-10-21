# applications/core/admin.py
from django.contrib import admin
from .models import (
    Sede, Deporte, SedeDeporte, Evento,
    Comunicado, Curso, Planificacion, PlanificacionVersion
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
    list_display = ("curso", "semana", "tiene_archivo", "autor", "creado")
    list_select_related = ("curso", "curso__sede", "curso__profesor", "curso__disciplina")
    list_filter = (
        "semana",
        "curso__programa",      # Formativo / Alto Rendimiento
        "curso__sede",
        "curso__disciplina",
    )
    search_fields = (
        "curso__nombre",
        "curso__profesor__first_name",
        "curso__profesor__last_name",
        "curso__sede__nombre",
    )
    date_hierarchy = "semana"
    ordering = ("-semana", "-creado")

    def tiene_archivo(self, obj):
        return bool(obj.archivo)
    tiene_archivo.boolean = True
    tiene_archivo.short_description = "Archivo"

@admin.register(PlanificacionVersion)
class PlanificacionVersionAdmin(admin.ModelAdmin):
    list_display = ("planificacion", "creado", "autor")
    list_select_related = ("planificacion", "planificacion__curso")
    search_fields = ("planificacion__curso__nombre", )
    date_hierarchy = "creado"
    ordering = ("-creado",)