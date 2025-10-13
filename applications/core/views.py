# applications/core/views.py
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import Comunicado

# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario


# ------- Home (informativo público) -------
@require_http_methods(["GET"])
def home(request):
    return render(request, "core/home.html")


# ------- Estudiantes -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def estudiantes_list(request):
    return render(request, "core/estudiantes_list.html")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Estudiantes - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Estudiantes - FORMULARIO CREAR (GET)")


# ------- Cursos / Cupos -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def cursos_list(request):
    return render(request, "core/cursos_list.html")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Cursos - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Cursos - FORMULARIO CREAR (GET)")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_configurar_cupos(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (POST) -> OK")
    return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (GET) -> formulario")


# ------- Profesores -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def profesores_list(request):
    return render(request, "core/profesores_list.html")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def profesor_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Profesores - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Profesores - FORMULARIO CREAR (GET)")


# ------- Planificación -------
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    if request.method == "POST":
        # luego guardaremos archivo y mes
        return HttpResponse("CORE / Planificación - SUBIR (POST) -> OK")
    return render(request, "core/planificacion_subir.html")


# ------- Autenticación (placeholders) -------
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == "POST":
        return HttpResponse("CORE / Login (POST) -> redirigir según rol")
    return HttpResponse("CORE / Login (GET) -> formulario")

@require_http_methods(["GET", "POST"])
def recuperar_password(request):
    if request.method == "POST":
        return HttpResponse("CORE / Recuperar Password (POST) -> clave provisoria enviada")
    return HttpResponse("CORE / Recuperar Password (GET) -> formulario")


# ------- Asistencia -------
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (GET) -> pantalla tomar asistencia")

@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def asistencia_estudiantes(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (GET) -> lista alumnos")


# ------- Ficha / Observaciones -------
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.PROF_MULT, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")


# ------- Comunicados -------
@role_required(
    Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF,
    Usuario.Tipo.APOD, Usuario.Tipo.ATLE, Usuario.Tipo.PROF_MULT
)
@require_http_methods(["GET"])
def comunicados_list(request):
    data = Comunicado.objects.all()[:50]
    return render(request, "core/comunicados_list.html", {"data": data})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PROF_MULT)
@require_http_methods(["GET", "POST"])
def comunicado_create(request):
    if request.method == "POST":
        titulo = (request.POST.get("titulo") or "").strip()
        cuerpo = (request.POST.get("cuerpo") or "").strip()
        if titulo and cuerpo:
            Comunicado.objects.create(titulo=titulo, cuerpo=cuerpo, autor=request.user)
            return redirect("core:comunicados_list")
        return render(request, "core/comunicado_create.html", {"error": "Completa título y cuerpo."})
    return render(request, "core/comunicado_create.html")


# ------- Reportes -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reporte_inasistencias(request):
    return HttpResponse("CORE / Reporte semanal de inasistencias (GET)")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request, clase_id: int):
    return HttpResponse(f"CORE / Reporte asistencia clase_id={clase_id} (GET)")


# ------- Páginas informativas -------
@require_http_methods(["GET"])
def quienes_somos(request):
    return render(request, "pages/quienes.html")

@require_http_methods(["GET"])
def procesos_inscripcion(request):
    return render(request, "pages/procesos.html")

@require_http_methods(["GET"])
def deportes_recintos(request):
    return render(request, "pages/deportes.html")

@require_http_methods(["GET"])
def equipo_multidisciplinario(request):
    return render(request, "pages/equipo.html")
