from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario

@role_required(Usuario.Tipo.PROF_MULT, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
def evaluaciones_list(request, estudiante_id: int):
    return HttpResponse(f"EVALUACIONES / Listar evaluaciones estudiante_id={estudiante_id} (GET)")

@role_required(Usuario.Tipo.PROF_MULT)
def evaluacion_create(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"EVALUACIONES / Crear evaluacion para estudiante_id={estudiante_id} (POST) -> guardado")
    return HttpResponse(f"EVALUACIONES / Formulario evaluacion para estudiante_id={estudiante_id} (GET)")
