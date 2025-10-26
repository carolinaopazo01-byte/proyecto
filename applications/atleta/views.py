# applications/atleta/views.py
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario

# ------- Agenda del Equipo Multidisciplinario -------
@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def agenda_disponible(request):
    return HttpResponse("ATLETA / Agenda disponible (GET) -> ver horarios y citas disponibles")


# ------- Crear Cita -------
@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def cita_crear(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Cita - CREAR (POST) -> agendada OK")
    return HttpResponse("ATLETA / Cita - FORMULARIO CREAR (GET)")


# ------- Proceso de Ingreso a Alto Rendimiento -------
@role_required(Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def proceso_ingreso_alto_rendimiento(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Proceso Ingreso AR (POST) -> paso guardado")
    return HttpResponse("ATLETA / Proceso Ingreso AR (GET) -> ver pasos/ficha/documentos")

@role_required(Usuario.Tipo.ATLE)
def panel(request):
    from datetime import date
    edad = (date.today() - request.user.fecha_nacimiento).days // 365
    if edad < 18:
        messages.error(request, "Acceso restringido a mayores de edad.")
        return redirect("usuarios:logout")
    return render(request, "atleta/panel.html", {"titulo": "Panel del Atleta"})
