from django.contrib import admin
from .models import Usuario, Coordinador, Profesor, ProfesionalMulti, Apoderado
from django.contrib.auth.admin import UserAdmin  # <<< importa esto

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Rol en el programa", {
            "fields": ("tipo_usuario", "equipo_rol"),
            "description": "Si 'tipo de usuario' es Equipo Multidisciplinario, selecciona el sub-rol."
        }),
    )
    list_display = ("username", "first_name", "last_name", "tipo_usuario", "equipo_rol", "is_active")
    list_filter = ("tipo_usuario", "equipo_rol", "is_active", "is_staff")

admin.site.register(Coordinador)
admin.site.register(Profesor)
admin.site.register(ProfesionalMulti)
admin.site.register(Apoderado)