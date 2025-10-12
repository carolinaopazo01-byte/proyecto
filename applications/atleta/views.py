from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def agenda_disponible(request):
    return HttpResponse("ATLETA / Agenda disponible (GET) -> ver horarios por profesional/especialidad")

@require_http_methods(["GET", "POST"])
def cita_crear(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Cita - CREAR (POST) -> agendada OK")
    return HttpResponse("ATLETA / Cita - FORMULARIO CREAR (GET)")

@require_http_methods(["GET", "POST"])
def proceso_ingreso_alto_rendimiento(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Proceso Ingreso AR (POST) -> paso guardado")
    return HttpResponse("ATLETA / Proceso Ingreso AR (GET) -> ver pasos/ficha/documentos")
