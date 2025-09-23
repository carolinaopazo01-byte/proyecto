from django.contrib import admin
from .models import Planificacion, Objetivo, Material, PlanificacionMaterial, Evaluacion, Cita

class ObjetivoInline(admin.TabularInline):
    model = Objetivo
    extra = 0

class PlanificacionMaterialInline(admin.TabularInline):
    model = PlanificacionMaterial
    extra = 0

@admin.register(Planificacion)
class PlanificacionAdmin(admin.ModelAdmin):
    list_display = ('nombre','mes','profesor')
    list_filter = ('mes','profesor')
    inlines = [ObjetivoInline, PlanificacionMaterialInline]

admin.site.register(Material)
admin.site.register(Evaluacion)
admin.site.register(Cita)
