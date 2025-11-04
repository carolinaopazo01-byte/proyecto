# applications/apoderado/services.py
from django.shortcuts import get_object_or_404
from applications.core.models import Estudiante  # ajusta import según tu app

def alumno_de_apoderado(user):
    """
    Devuelve el alumno asociado al apoderado (request.user).
    Si tienes varios alumnos por apoderado, cambia a .filter(...) y maneja elección.
    """
    return get_object_or_404(
        Estudiante.objects.select_related("apoderado", "apoderado__usuario"),
        apoderado__usuario=user
    )
