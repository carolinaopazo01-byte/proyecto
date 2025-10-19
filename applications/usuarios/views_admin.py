from django.shortcuts import render, redirect
from applications.usuarios.models import Usuario
from applications.usuarios.utils import role_required

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def panel_admin(request):
    return render(request, "usuarios/panel_admin.html", {
        "tiles": [
            {"titulo": "Cursos", "url": "core:cursos_list"},
            {"titulo": "Estudiantes", "url": "core:estudiantes_list"},
            {"titulo": "Planificación", "url": "core:planificaciones_list"},
            {"titulo": "Reportes", "url": "core:reportes_home"},
            {"titulo": "Sedes", "url": "core:sedes_list"},
            {"titulo": "Deportes", "url": "core:deportes_list"},
            {"titulo": "Equipo Multidisciplinario", "url": "usuarios:equipo_list"},
        ]
    })
