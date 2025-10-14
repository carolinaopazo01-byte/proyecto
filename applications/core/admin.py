from django.contrib import admin
from .models import Sede, Deporte, SedeDeporte, Evento, Comunicado, Curso

# Estos se registran de forma simple
admin.site.register(Sede)
admin.site.register(Deporte)
admin.site.register(SedeDeporte)
admin.site.register(Evento)

# Comunicado: usa un ModelAdmin (no lo registres dos veces)
@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "creado")
    search_fields = ("titulo", "cuerpo")

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "programa", "disciplina", "profesor", "sede", "cupos", "publicado")
    list_filter = ("programa", "publicado", "disciplina", "sede")
    search_fields = ("nombre", "profesor__username")