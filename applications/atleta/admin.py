from django.contrib import admin
from .models import Atleta, Inscripcion, Clase, AsistenciaAtleta, AsistenciaProfesor, Cita

class AsistenciaAtletaInline(admin.TabularInline):
    model = AsistenciaAtleta
    extra = 0

@admin.register(Clase)
class ClaseAdmin(admin.ModelAdmin):
    list_display = ('sede_deporte','profesor','fecha','hora_inicio','hora_fin','tema')
    list_filter = ('sede_deporte','profesor','fecha')
    inlines = [AsistenciaAtletaInline]

@admin.register(Atleta)
class AtletaAdmin(admin.ModelAdmin):
    list_display = ('usuario','rut','tipo_atleta','faltas_consecutivas')
    search_fields = ('usuario__username','rut')

admin.site.register(Inscripcion)
admin.site.register(AsistenciaProfesor)

# applications/atleta/admin.py
from django.contrib import admin
from .models import Cita  # <- nombre correcto del modelo

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "hora", "profesional", "paciente", "estado")
    list_filter = ("estado", "fecha")
    search_fields = ("profesional__username", "paciente__username")
elds = ("profesional__username", "paciente__username")