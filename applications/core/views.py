# applications/core/views.py
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from .models import Comunicado, Curso, Sede, Estudiante, Planificacion, Deporte
from .forms import PlanificacionForm, DeporteForm  # EstudianteForm se importa perezoso en las vistas

# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario


# ------- Home (informativo) -------
@require_http_methods(["GET"])
def home(request):
    return render(request, "core/home.html")


# ================= ESTUDIANTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def estudiantes_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Estudiante.objects.all().order_by("apellidos", "nombres")
    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(email__icontains=q)
        )
    return render(request, "core/estudiantes_list.html", {"estudiantes": qs, "q": q})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create(request):
    # import perezoso para evitar problemas durante makemigrations
    from .forms import EstudianteForm
    if request.method == "POST":
        form = EstudianteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm()
    return render(request, "core/estudiante_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_edit(request, estudiante_id: int):
    from .forms import EstudianteForm
    obj = get_object_or_404(Estudiante, pk=estudiante_id)
    if request.method == "POST":
        form = EstudianteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm(instance=obj)
    return render(request, "core/estudiante_form.html", {"form": form, "is_edit": True, "estudiante": obj})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def estudiante_delete(request, estudiante_id: int):
    Estudiante.objects.filter(pk=estudiante_id).delete()
    return redirect("core:estudiantes_list")


# ================= CURSOS =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def cursos_list(request):
    cursos = Curso.objects.select_related("sede", "profesor").all()
    return render(request, "core/cursos_list.html", {"cursos": cursos})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_create(request):
    from .forms import CursoForm
    if request.method == "POST":
        form = CursoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm()
    return render(request, "core/curso_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_edit(request, curso_id: int):
    from .forms import CursoForm
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method == "POST":
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm(instance=curso)
    return render(request, "core/curso_form.html", {"form": form, "is_edit": True, "curso": curso})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def curso_delete(request, curso_id: int):
    Curso.objects.filter(pk=curso_id).delete()
    return redirect("core:cursos_list")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_configurar_cupos(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (POST) -> OK")
    return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (GET) -> formulario")


# ================= SEDES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def sedes_list(request):
    sedes = Sede.objects.all().order_by("nombre")
    return render(request, "core/sedes_list.html", {"sedes": sedes})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def sede_create(request):
    from .forms import SedeForm
    if request.method == "POST":
        form = SedeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:sedes_list")
    else:
        form = SedeForm()
    return render(request, "core/sede_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def sede_edit(request, sede_id: int):
    from .forms import SedeForm
    sede = get_object_or_404(Sede, pk=sede_id)
    if request.method == "POST":
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            form.save()
            return redirect("core:sedes_list")
    else:
        form = SedeForm(instance=sede)
    return render(request, "core/sede_form.html", {"form": form, "is_edit": True, "sede": sede})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def sede_delete(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)
    sede.delete()
    return redirect("core:sedes_list")


# ================= COMUNICADOS =================
@role_required(
    Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF,
    Usuario.Tipo.APOD, Usuario.Tipo.ATLE, Usuario.Tipo.PMUL
)
@require_http_methods(["GET"])
def comunicados_list(request):
    data = Comunicado.objects.all().order_by("-creado")[:50]
    return render(request, "core/comunicados_list.html", {"data": data})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
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


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
@require_http_methods(["GET", "POST"])
def comunicado_edit(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if request.user != com.autor and request.user.tipo_usuario not in [Usuario.Tipo.ADMIN, Usuario.Tipo.COORD]:
        return HttpResponse("No tienes permisos para editar este comunicado.", status=403)
    if request.method == "POST":
        titulo = (request.POST.get("titulo") or "").strip()
        cuerpo = (request.POST.get("cuerpo") or "").strip()
        if titulo and cuerpo:
            com.titulo, com.cuerpo = titulo, cuerpo
            com.save()
            return redirect("core:comunicados_list")
        return render(request, "core/comunicado_edit.html", {"comunicado": com, "error": "Completa título y cuerpo."})
    return render(request, "core/comunicado_edit.html", {"comunicado": com})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
@require_http_methods(["POST"])
def comunicado_delete(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if request.user != com.autor and request.user.tipo_usuario not in [Usuario.Tipo.ADMIN, Usuario.Tipo.COORD]:
        return HttpResponse("No tienes permisos para eliminar este comunicado.", status=403)
    com.delete()
    return redirect("core:comunicados_list")


# ================ Páginas informativas ================
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


# ------- Profesores (stubs mínimos para que no falle urls) -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def profesores_list(request):
    return render(request, "core/profesores_list.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def profesor_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Profesores - CREAR (POST) -> guardado OK")
    return render(request, "core/profesor_form.html")


# -------- STUBS QUE PUEDEN FALTAR EN URLs --------
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    if request.method == "POST":
        return HttpResponse("CORE / Planificación - SUBIR (POST) -> OK")
    return HttpResponse("CORE / Planificación - SUBIR (GET) -> formulario simple")


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


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")


# ================= REPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reportes_home(request):
    """Página de entrada a los reportes (menú simple con links)."""
    return render(request, "core/reportes_home.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reporte_inasistencias(request):
    return HttpResponse("CORE / Reporte semanal de inasistencias (GET)")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request, clase_id: int):
    return HttpResponse(f"CORE / Reporte asistencia clase_id={clase_id} (GET)")


# ================= PLANIFICACIONES =================
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def planificaciones_list(request):
    qs = Planificacion.objects.order_by("-creado")
    return render(request, "core/planificaciones_list.html", {"items": qs})


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def planificacion_create(request):
    if request.method == "POST":
        form = PlanificacionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.autor = request.user if request.user.is_authenticated else None
            obj.save()
            return redirect("core:planificaciones_list")
    else:
        form = PlanificacionForm()
    return render(request, "core/planificacion_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def planificacion_edit(request, plan_id: int):
    obj = get_object_or_404(Planificacion, pk=plan_id)
    if request.method == "POST":
        form = PlanificacionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:planificaciones_list")
    else:
        form = PlanificacionForm(instance=obj)
    return render(request, "core/planificacion_form.html", {"form": form, "is_edit": True, "obj": obj})


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def planificacion_delete(request, plan_id: int):
    obj = get_object_or_404(Planificacion, pk=plan_id)
    obj.delete()
    return redirect("core:planificaciones_list")


# ================= DEPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def deportes_list(request):
    items = Deporte.objects.all().order_by("nombre")
    return render(request, "core/deportes_list.html", {"items": items})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def deporte_create(request):
    if request.method == "POST":
        form = DeporteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:deportes_list")
    else:
        form = DeporteForm()
    return render(request, "core/deporte_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def deporte_edit(request, deporte_id: int):
    obj = get_object_or_404(Deporte, pk=deporte_id)
    if request.method == "POST":
        form = DeporteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:deportes_list")
    else:
        form = DeporteForm(instance=obj)
    return render(request, "core/deporte_form.html", {"form": form, "is_edit": True, "obj": obj})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def deporte_delete(request, deporte_id: int):
    get_object_or_404(Deporte, pk=deporte_id).delete()
    return redirect("core:deportes_list")
