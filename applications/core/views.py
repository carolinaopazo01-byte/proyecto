# applications/core/views.py
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

def home(request):
    ctx = {"next_url": reverse("core:estudiantes_list")}
    return render(request, "core/home.html", ctx)

# ------- Estudiantes -------
@require_http_methods(["GET"])
def estudiantes_list(request):
    return render(request, "core/estudiantes_list.html", {"next_url": reverse("core:cursos_list")})

@require_http_methods(["GET", "POST"])
def estudiante_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Estudiantes - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Estudiantes - FORMULARIO CREAR (GET)")

# ------- Cursos / Cupos -------
@require_http_methods(["GET"])
def cursos_list(request):
    return render(request, "core/cursos_list.html", {"next_url": reverse("core:profesores_list")})

@require_http_methods(["GET", "POST"])
def curso_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Cursos - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Cursos - FORMULARIO CREAR (GET)")

@require_http_methods(["POST"])
def curso_configurar_cupos(request, curso_id: int):
    return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (POST) -> OK")

# ------- Profesores -------
@require_http_methods(["GET"])
def profesores_list(request):
    return render(request, "core/profesores_list.html", {"next_url": reverse("core:planificacion_upload")})

@require_http_methods(["GET", "POST"])
def profesor_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Profesores - CREAR (POST) -> guardado OK")
    return HttpResponse("CORE / Profesores - FORMULARIO CREAR (GET)")

# ------- Planificación -------
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    if request.method == "POST":
        return HttpResponse("CORE / Planificación - SUBIR (POST) -> OK")
    ctx = {"next_url": reverse("core:comunicados_list")}
    return render(request, "core/planificacion_subir.html", ctx)

# ------- Auth -------
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
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (GET) -> pantalla tomar asistencia")

@require_http_methods(["GET", "POST"])
def asistencia_estudiantes(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (GET) -> lista alumnos")

# ------- Ficha / Observaciones -------
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")

# ------- Comunicados -------
@require_http_methods(["GET"])
def comunicados_list(request):
    return render(request, "core/comunicados_list.html", {"next_url": reverse("core:cursos_list")})

@require_http_methods(["GET", "POST"])
def comunicado_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Comunicados - CREAR (POST) -> enviado")
    return HttpResponse("CORE / Comunicados - FORMULARIO CREAR (GET)")

# ------- Reportes -------
@require_http_methods(["GET"])
def reporte_inasistencias(request):
    return HttpResponse("CORE / Reporte semanal de inasistencias (GET)")

@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request, clase_id: int):
    return HttpResponse(f"CORE / Reporte asistencia clase_id={clase_id} (GET)")
##################################
def quienes_somos(request):
    return render(request, "pages/quienes.html")

def procesos_inscripcion(request):
    return render(request, "pages/procesos.html")

def deportes_recintos(request):
    return render(request, "pages/deportes.html")

def equipo_multidisciplinario(request):
    return render(request, "pages/equipo.html")
def home(request):
    return render(request, "core/home.html")  # sin next_url