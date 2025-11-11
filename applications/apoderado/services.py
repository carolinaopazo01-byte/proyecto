# applications/apoderado/services.py
from django.shortcuts import get_object_or_404
from applications.core.models import Estudiante

def alumno_de_apoderado(user):

    return get_object_or_404(
        Estudiante.objects.select_related("apoderado", "apoderado__usuario"),
        apoderado__usuario=user
    )
