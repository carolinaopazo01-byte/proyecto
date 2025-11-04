from django.contrib import admin
from .models import ProfesionalPerfil, Cita, FichaClinica, FichaAdjunto

@admin.register(ProfesionalPerfil)
class ProfesionalPerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "especialidad")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    list_filter = ("especialidad",)

@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "profesional", "inicio", "estado", "piso")
    list_filter = ("estado", "piso", "especialidad")
    search_fields = ("paciente__nombres", "paciente__apellidos", "profesional__username")

@admin.register(FichaClinica)
class FichaClinicaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "profesional", "fecha", "estado", "especialidad")
    list_filter = ("estado", "especialidad", "fecha")
    search_fields = ("paciente__nombres", "paciente__apellidos", "profesional__username")

@admin.register(FichaAdjunto)
class FichaAdjuntoAdmin(admin.ModelAdmin):
    list_display = ("ficha", "nombre", "archivo")
