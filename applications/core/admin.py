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

from django.contrib import admin
from django import forms
from .models import Comunicado, Audiencia

class ComunicadoAdminForm(forms.ModelForm):
    audiencia_codigos_multi = forms.MultipleChoiceField(
        label="Audiencia",
        required=False,
        choices=Audiencia.choices,
        widget=forms.CheckboxSelectMultiple
    )
    class Meta:
        model = Comunicado
        fields = ["titulo","cuerpo","autor","audiencia_codigos_multi","audiencia_roles"]

    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.fields["audiencia_codigos_multi"].initial = self.instance.get_audiencia_codigos()

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.set_audiencia_codigos(self.cleaned_data.get("audiencia_codigos_multi"))
        if commit: obj.save(); self.save_m2m()
        return obj

@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    form = ComunicadoAdminForm
    list_display = ("titulo","autor","creado","_es_publico")
    search_fields = ("titulo","cuerpo","audiencia_codigos")
    def _es_publico(self,obj): return obj.es_publico


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