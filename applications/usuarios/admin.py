from django.contrib import admin
from .models import Usuario, Coordinador, Profesor, ProfesionalMulti, Apoderado

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('username', 'rut', 'tipo_usuario', 'is_active')
    search_fields = ('username', 'rut', 'first_name', 'last_name')

admin.site.register(Coordinador)
admin.site.register(Profesor)
admin.site.register(ProfesionalMulti)
admin.site.register(Apoderado)
