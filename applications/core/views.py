# applications/core/views.py
import os
from datetime import date, timedelta
from math import radians, sin, cos, asin, sqrt
from io import BytesIO
import base64
import matplotlib.pyplot as plt
import pandas as pd
from weasyprint import HTML
from django.template.loader import render_to_string
from django.db.models.functions import TruncMonth

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.db.models.deletion import ProtectedError
from django.http import (
    HttpResponse, FileResponse, Http404, HttpResponseForbidden
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario, Profesor
from applications.atleta.models import Clase, AsistenciaAtleta

from .models import (
    Comunicado, Curso, Sede, Estudiante, Planificacion,
    Deporte, PlanificacionVersion, Noticia, RegistroPeriodo
)
from .forms import (
    DeporteForm, PlanificacionUploadForm, ComunicadoForm,
    NoticiaForm, EstudianteForm
)

# -------- Helpers --------
def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _es_prof(user) -> bool:
    return getattr(user, "tipo_usuario", None) == Usuario.Tipo.PROF


def _is_admin_or_coord(user) -> bool:
    return getattr(user, "tipo_usuario", None) in (Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)


def _periodo_abierto():
    """
    Retorna el último RegistroPeriodo abierto para público:
    activo=True, estado=OPEN y dentro de rango de fechas (si existen).
    (OJO: usamos Q importado de django.db.models, no el módulo .models)
    """
    now = timezone.now()
    qs = RegistroPeriodo.objects.filter(
        activo=True,
        estado=RegistroPeriodo.Estado.ABIERTA,
    )
    qs = qs.filter(Q(inicio__isnull=True) | Q(inicio__lte=now))
    qs = qs.filter(Q(fin__isnull=True) | Q(fin__gte=now))
    return qs.order_by("-creado").first()


# -------- Back-to helper (HTML-only) --------
def _back_to_url(request, fallback_name: str) -> str:
    """
    Orden de preferencia (sin JS):
    1) ?next=...
    2) HTTP_REFERER
    3) reverse(fallback_name)
    """
    nxt = (request.GET.get("next") or "").strip()
    if nxt:
        return nxt
    ref = (request.META.get("HTTP_REFERER") or "").strip()
    if ref:
        return ref
    try:
        return reverse(fallback_name)
    except Exception:
        # Si te pasan un path directo como fallback_name, úsalo tal cual.
        return fallback_name


# === Helper: obtener alumnos de un curso, con o sin tabla de inscripciones ===
def _estudiantes_del_curso(curso):
    """
    Devuelve los estudiantes asociados al curso.
    Funciona tanto con InscripcionCurso como con la FK directa curso en Estudiante.
    """
    EstudianteModel = apps.get_model('core', 'Estudiante')

    # 1) Si existe modelo InscripcionCurso
    try:
        InscripcionCurso = apps.get_model('core', 'InscripcionCurso')
        if InscripcionCurso:
            ins = (InscripcionCurso.objects
                   .filter(curso=curso)
                   .select_related("estudiante__usuario"))
            if ins.exists():
                return [i.estudiante for i in ins]
    except Exception:
        pass

    # 2) Si el curso tiene relación directa (FK) con Estudiante
    try:
        directos = EstudianteModel.objects.filter(curso=curso, activo=True).select_related("usuario")
        if directos.exists():
            return list(directos)
    except Exception:
        pass

    # 3) Relación M2M genérica
    for attr in ("estudiantes", "alumnos", "inscritos"):
        if hasattr(curso, attr):
            try:
                return list(getattr(curso, attr).all().select_related("usuario"))
            except Exception:
                return list(getattr(curso, attr).all())

    return EstudianteModel.objects.none()


# ------- Home (informativo) -------
@require_http_methods(["GET"])
def home(request):
    noticias_slider = (
        Noticia.objects.filter(publicada=True)
        .exclude(imagen="").exclude(imagen__isnull=True)
        .order_by("-publicada_en", "-creado")[:6]
    )
    noticias = (
        Noticia.objects.filter(publicada=True)
        .order_by("-publicada_en", "-creado")[:6]
    )
    return render(
        request,
        "core/home.html",
        {
            "noticias_slider": noticias_slider,
            "noticias": noticias,
        },
    )


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
    page_number = request.GET.get("page") or 1
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "core/estudiantes_list.html",
        {
            "estudiantes": page_obj,
            "q": q,
            "page_obj": page_obj,
        },
    )


# --- (Opcional) Listado visible para PROF: muestra solo sus alumnos ---
@role_required(Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def estudiantes_list_prof(request):
    q = (request.GET.get("q") or "").strip()
    # alumnos asociados a los cursos donde el request.user es profesor
    qs = Estudiante.objects.filter(
        Q(curso__profesor=request.user) | Q(curso__profesores_apoyo=request.user)
    ).distinct().order_by("apellidos", "nombres")
    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(email__icontains=q)
        )
    page_number = request.GET.get("page") or 1
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "core/estudiantes_list.html",  # reutilizamos la misma plantilla
        {
            "estudiantes": page_obj,
            "q": q,
            "page_obj": page_obj,
        },
    )


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create(request):
    if request.method == "POST":
        form = EstudianteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm()
    ctx = {
        "form": form,
        "is_edit": False,
        "show_back": True,
        "back_to": _back_to_url(request, "core:estudiantes_list"),
    }
    return render(request, "core/estudiante_form.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_edit(request, estudiante_id: int):
    obj = get_object_or_404(Estudiante, pk=estudiante_id)
    if request.method == "POST":
        form = EstudianteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm(instance=obj)
    ctx = {
        "form": form,
        "is_edit": True,
        "estudiante": obj,
        "show_back": True,
        "back_to": _back_to_url(request, "core:estudiantes_list"),
    }
    return render(request, "core/estudiante_form.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def estudiante_delete(request, estudiante_id: int):
    obj = get_object_or_404(Estudiante, pk=estudiante_id)
    obj.delete()
    messages.success(request, "Estudiante eliminado.")
    return redirect("core:estudiantes_list")


# ================= CURSOS =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def cursos_list(request):
    cursos = (
        Curso.objects
        .select_related("sede", "profesor", "disciplina")
        .prefetch_related("horarios")
        .all()
    )
    return render(request, "core/cursos_list.html", {"cursos": cursos})


# === Mis cursos (perfil profesor) ===
@role_required(Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def cursos_mios(request):
    cursos = (
        Curso.objects
        .select_related("sede", "profesor", "disciplina")
        .prefetch_related("horarios")  # usa "cursohorario_set" si no definiste related_name
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .distinct()
    )
    return render(request, "core/cursos_list.html", {"cursos": cursos})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_create(request):
    from .forms import CursoForm, CursoHorarioFormSet
    if request.method == "POST":
        form = CursoForm(request.POST)
        formset = CursoHorarioFormSet(request.POST, prefix="horarios")  # 👈 prefijo fijo
        if form.is_valid() and formset.is_valid():
            curso = form.save()
            formset.instance = curso
            formset.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm()
        formset = CursoHorarioFormSet(prefix="horarios")  # 👈 prefijo fijo
    return render(request, "core/curso_form.html", {
        "form": form, "formset": formset, "is_edit": False,
        "show_back": True,
        "back_to": _back_to_url(request, "core:cursos_list"),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_edit(request, curso_id: int):
    from .forms import CursoForm, CursoHorarioFormSet
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method == "POST":
        form = CursoForm(request.POST, instance=curso)
        formset = CursoHorarioFormSet(request.POST, instance=curso, prefix="horarios")  # 👈 prefijo fijo
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm(instance=curso)
        formset = CursoHorarioFormSet(instance=curso, prefix="horarios")  # 👈 prefijo fijo
    return render(request, "core/curso_form.html", {
        "form": form, "formset": formset, "is_edit": True, "curso": curso,
        "show_back": True,
        "back_to": _back_to_url(request, "core:cursos_list"),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def curso_delete(request, curso_id: int):
    obj = get_object_or_404(Curso, pk=curso_id)
    obj.delete()
    messages.success(request, "Curso eliminado.")
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
    q = (request.GET.get("q") or "").strip()
    comuna = (request.GET.get("comuna") or "").strip()
    estado = (request.GET.get("estado") or "").strip()  # act | inact | ""
    cap_cmp = (request.GET.get("cap_cmp") or "").strip()  # gt | lt | ""
    try:
        cap_val = int(request.GET.get("cap_val") or 0)
    except ValueError:
        cap_val = 0

    qs = Sede.objects.all().order_by("nombre")

    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(comuna__icontains=q))
    if comuna:
        qs = qs.filter(comuna__iexact=comuna)
    if estado == "act":
        qs = qs.filter(activa=True)
    elif estado == "inact":
        qs = qs.filter(activa=False)
    if cap_cmp == "gt" and cap_val:
        qs = qs.filter(capacidad__gte=cap_val)
    elif cap_cmp == "lt" and cap_val:
        qs = qs.filter(capacidad__lte=cap_val)

    comunas = Sede.objects.exclude(comuna="").values_list("comuna", flat=True).distinct().order_by("comuna")
    return render(request, "core/sedes_list.html", {
        "sedes": qs,
        "q": q,
        "comuna_sel": comuna,
        "estado_sel": estado,
        "cap_cmp": cap_cmp,
        "cap_val": cap_val or "",
        "comunas": comunas,
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def sede_detail(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)
    return render(request, "core/sede_detail.html", {"sede": sede})


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
        form = SedeForm(initial={"comuna": "Coquimbo"})
    return render(request, "core/sede_form.html", {"form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:sedes_list")})


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
    return render(request, "core/sede_form.html", {"form": form, "is_edit": True, "sede": sede,
        "show_back": True, "back_to": _back_to_url(request, "core:sedes_list")})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def sede_delete(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)
    try:
        sede.delete()
        messages.success(request, "Sede eliminada.")
    except ProtectedError:
        messages.error(request, "No se puede eliminar la sede: tiene cursos o clases asociados.")
    return redirect("core:sedes_list")


# ================= COMUNICADOS =================
@role_required(
    Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF,
    Usuario.Tipo.APOD, Usuario.Tipo.ATLE, Usuario.Tipo.PMUL
)
@require_http_methods(["GET"])
def comunicados_list(request):
    comunicados = None
    try:
        if hasattr(Comunicado.objects, "for_user"):
            comunicados = Comunicado.objects.for_user(request.user).order_by("-creado", "-id")[:50]
    except Exception:
        comunicados = None

    if comunicados is None:
        if hasattr(Comunicado, "creado"):
            comunicados = Comunicado.objects.all().order_by("-creado", "-id")[:50]
        elif hasattr(Comunicado, "fecha"):
            comunicados = Comunicado.objects.all().order_by("-fecha", "-id")[:50]
        elif hasattr(Comunicado, "created_at"):
            comunicados = Comunicado.objects.all().order_by("-created_at", "-id")[:50]
        else:
            comunicados = Comunicado.objects.all().order_by("-id")[:50]

    return render(request, "core/comunicados_list.html", {
        "comunicados": comunicados,
        "puede_crear": _is_admin_or_coord(request.user),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def comunicado_create(request):
    form = ComunicadoForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.autor = request.user
            obj.save()
            form.save_m2m()
            messages.success(request, "Comunicado creado correctamente.")
            return redirect("core:comunicados_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/comunicado_create.html", {
        "form": form,
        "show_back": True, "back_to": _back_to_url(request, "core:comunicados_list")
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def comunicado_edit(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if not _is_admin_or_coord(request.user):
        return HttpResponse("No tienes permisos para editar este comunicado.", status=403)
    form = ComunicadoForm(request.POST or None, instance=com)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Comunicado actualizado.")
            return redirect("core:comunicados_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/comunicado_edit.html", {
        "form": form, "comunicado": com,
        "show_back": True, "back_to": _back_to_url(request, "core:comunicados_list")
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def comunicado_delete(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if not _is_admin_or_coord(request.user):
        return HttpResponse("No tienes permisos para eliminar este comunicado.", status=403)
    com.delete()
    messages.success(request, "Comunicado eliminado.")
    return redirect("core:comunicados_list")


# =================== NOTICIAS (SOLO ADMIN) ===================
@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def noticias_list(request):
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()  # "pub" | "nopub" | ""
    qs = Noticia.objects.all().order_by("-creado")
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(bajada__icontains=q))
    if estado == "pub":
        qs = qs.filter(publicada=True)
    elif estado == "nopub":
        qs = qs.filter(publicada=False)

    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)
    return render(request, "core/noticias_list.html", {
        "page_obj": page_obj,
        "q": q,
        "estado": estado,
    })


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def noticia_create(request):
    form = NoticiaForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.autor = request.user
            if obj.publicada and not obj.publicada_en:
                obj.publicada_en = timezone.now()
            obj.save()
            messages.success(request, "Noticia creada correctamente.")
            return redirect("core:noticias_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/noticia_form.html", {
        "form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:noticias_list")
    })


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def noticia_edit(request, noticia_id: int):
    obj = get_object_or_404(Noticia, pk=noticia_id)
    form = NoticiaForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            prev_publicada = obj.publicada
            noticia = form.save(commit=False)
            if noticia.publicada and not prev_publicada:
                noticia.publicada_en = timezone.now()
            if not noticia.publicada:
                noticia.publicada_en = None
            noticia.save()
            messages.success(request, "Noticia actualizada.")
            return redirect("core:noticias_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/noticia_form.html", {
        "form": form, "is_edit": True, "obj": obj,
        "show_back": True, "back_to": _back_to_url(request, "core:noticias_list")
    })


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def noticia_delete(request, noticia_id: int):
    obj = get_object_or_404(Noticia, pk=noticia_id)
    obj.delete()
    messages.success(request, "Noticia eliminada.")
    return redirect("core:noticias_list")


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def noticia_toggle_publicar(request, noticia_id: int):
    obj = get_object_or_404(Noticia, pk=noticia_id)
    obj.publicada = not obj.publicada
    obj.publicada_en = timezone.now() if obj.publicada else None
    obj.save(update_fields=["publicada", "publicada_en"])
    estado = "publicada" if obj.publicada else "despublicada"
    messages.success(request, f"Noticia {estado}.")
    return redirect("core:noticias_list")


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


# ===== Registro público (POSTULACIÓN) =====
@require_http_methods(["GET", "POST"])
def registro_publico(request):
    from .forms import RegistroPublicoForm
    periodo = _periodo_abierto()

    if request.method == "POST":
        form = RegistroPublicoForm(request.POST)
        if not periodo:
            now = timezone.now()
            proximos = (RegistroPeriodo.objects
                        .filter(activo=True)
                        .exclude(estado=RegistroPeriodo.Estado.CERRADA)
                        .filter(Q(inicio__gt=now) | Q(inicio__isnull=True))
                        .order_by("inicio")[:5])
            messages.error(request, "Las postulaciones no están abiertas en este momento.")
            return render(request, "core/registro_cerrado.html", {"proximos": proximos}, status=403)

        if form.is_valid():
            obj = form.save(commit=False)
            # si el modelo de la forma tiene FK periodo, lo asignamos
            if hasattr(obj, "periodo"):
                obj.periodo = periodo
            obj.save()
            messages.success(request, "¡Tu postulación fue enviada! Te contactaremos pronto.")
            return redirect("core:procesos_inscripcion")
    else:
        if not periodo:
            now = timezone.now()
            proximos = (RegistroPeriodo.objects
                        .filter(activo=True)
                        .exclude(estado=RegistroPeriodo.Estado.CERRADA)
                        .filter(Q(inicio__gt=now) | Q(inicio__isnull=True))
                        .order_by("inicio")[:5])
            return render(request, "core/registro_cerrado.html", {"proximos": proximos}, status=403)
        form = RegistroPublicoForm()

    return render(request, "core/registro_form.html", {
        "form": form,
        "show_back": True,
        "back_to": _back_to_url(request, "core:procesos_inscripcion"),
    })


# ------- Profesores (stubs mínimos) -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def profesores_list(request):
    return render(request, "core/profesores_list.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def profesor_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Profesores - CREAR (POST) -> guardado OK")
    return render(request, "core/profesor_form.html", {
        "show_back": True,
        "back_to": _back_to_url(request, "core:profesores_list"),
    })


# ================= PLANIFICACIONES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificaciones_list(request):
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = _monday(base)

    programa = (request.GET.get("programa") or "").strip()
    sede_id = (request.GET.get("sede") or "")
    dep_id = (request.GET.get("disciplina") or "")
    curso_id = (request.GET.get("curso") or "")
    prof_id = (request.GET.get("prof") or "")

    cursos_qs = Curso.objects.select_related("sede", "profesor", "disciplina").all()
    if programa:
        cursos_qs = cursos_qs.filter(programa=programa)
    if sede_id:
        cursos_qs = cursos_qs.filter(sede_id=sede_id)
    if dep_id:
        cursos_qs = cursos_qs.filter(disciplina_id=dep_id)
    if curso_id:
        cursos_qs = cursos_qs.filter(id=curso_id)
    if prof_id:
        cursos_qs = cursos_qs.filter(profesor_id=prof_id)
    total_cursos = cursos_qs.count()

    plans = (Planificacion.objects
             .select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")
             .filter(semana=lunes))

    if programa:
        plans = plans.filter(curso__programa=programa)
    if sede_id:
        plans = plans.filter(curso__sede_id=sede_id)
    if dep_id:
        plans = plans.filter(curso__disciplina_id=dep_id)
    if curso_id:
        plans = plans.filter(curso_id=curso_id)
    if prof_id:
        plans = plans.filter(curso__profesor_id=prof_id)

    cursos_con_plan = plans.values("curso_id").distinct().count()
    pct_subidas = round((cursos_con_plan / total_cursos) * 100, 1) if total_cursos else 0.0

    ctx = {
        "semana": base.isoformat(),
        "lunes": lunes,
        "total_cursos": total_cursos,
        "pct_subidas": pct_subidas,
        "items": plans.order_by("curso__sede__nombre", "curso__disciplina__nombre", "curso__nombre"),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "cursos": cursos_qs.order_by("nombre"),
        "profes": Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).order_by("last_name", "first_name"),
        "programa": programa,
        "sede_id": sede_id,
        "dep_id": dep_id,
        "curso_id": curso_id,
        "prof_id": prof_id,
    }
    return render(request, "core/planificaciones_list.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    if request.method == "POST":
        form = PlanificacionUploadForm(request.POST, request.FILES, user=getattr(request, "user", None))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.semana = _monday(obj.semana)
            obj.autor = request.user

            with transaction.atomic():
                existente = Planificacion.objects.select_for_update().filter(
                    curso=obj.curso, semana=obj.semana
                ).first()
                if existente:
                    new_version_num = existente.versiones.count() + 1
                    if existente.archivo:
                        PlanificacionVersion.objects.create(
                            planificacion=existente,
                            archivo=existente.archivo,
                            autor=request.user,
                        )
                    existente.archivo = obj.archivo or existente.archivo
                    existente.comentarios = getattr(obj, "comentarios", "")
                    existente.publica = getattr(obj, "publica", False)
                    existente.autor = request.user
                    existente.save()
                    messages.warning(request, f"Se creó versión {new_version_num} para esa semana.")
                else:
                    obj.save()
                    messages.success(request, f"Planificación de la semana {obj.semana:%d-%m-%Y} publicada.")
            return redirect("core:planificaciones_list")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = PlanificacionUploadForm(user=request.user)

    return render(request, "core/planificacion_form_upload.html", {
        "form": form,
        "show_back": True, "back_to": _back_to_url(request, "core:planificaciones_list")
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_detail(request, plan_id: int):
    p = get_object_or_404(
        Planificacion.objects.select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina"),
        pk=plan_id
    )
    return render(request, "core/planificacion_detail.html", {"p": p})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_download(request, plan_id: int):
    p = get_object_or_404(Planificacion, pk=plan_id)
    if not p.archivo:
        raise Http404("No hay archivo para descargar.")
    return FileResponse(p.archivo.open("rb"), as_attachment=True, filename=os.path.basename(p.archivo.name))


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_historial(request, plan_id: int):
    p = get_object_or_404(Planificacion, pk=plan_id)
    versiones = p.versiones.all()
    return render(request, "core/planificacion_historial.html", {"p": p, "versiones": versiones})


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
    return render(request, "core/deporte_form.html", {
        "form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:deportes_list")
    })


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
    return render(request, "core/deporte_form.html", {
        "form": form, "is_edit": True, "obj": obj,
        "show_back": True, "back_to": _back_to_url(request, "core:deportes_list")
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def deporte_delete(request, deporte_id: int):
    get_object_or_404(Deporte, pk=deporte_id).delete()
    return redirect("core:deportes_list")


# ================= REPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_home(request):
    return render(request, "core/reportes_home.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reportes_kpi(request):
    """
    Dashboard integral CPC con KPI filtrables por sede, programa y disciplina.
    Todos los indicadores se consultan directamente desde la base de datos.
    """
    from django.db.models import Count, Q
    from django.db.models.functions import TruncMonth
    from datetime import date
    from applications.usuarios.models import Usuario
    from applications.core.models import (
        Estudiante, Curso, Sede, Planificacion,
        AsistenciaCurso, AsistenciaCursoDetalle
    )

    # === Parámetros de filtro ===
    programa = (request.GET.get("programa") or "").strip()
    sede_id = request.GET.get("sede") or ""
    dep_id = request.GET.get("disciplina") or ""

    # === QuerySets base ===
    est_qs = Estudiante.objects.all()
    curso_qs = Curso.objects.all()
    plan_qs = Planificacion.objects.all()
    asis_qs = AsistenciaCurso.objects.all()
    asis_det_qs = AsistenciaCursoDetalle.objects.all()

    # === Filtros (ajustados a los modelos reales) ===
    if programa:
        est_qs = est_qs.filter(curso__programa=programa)
        curso_qs = curso_qs.filter(programa=programa)
        plan_qs = plan_qs.filter(curso__programa=programa)
        asis_qs = asis_qs.filter(curso__programa=programa)
        asis_det_qs = asis_det_qs.filter(asistencia__curso__programa=programa)

    if sede_id:
        est_qs = est_qs.filter(curso__sede_id=sede_id)
        curso_qs = curso_qs.filter(sede_id=sede_id)
        plan_qs = plan_qs.filter(curso__sede_id=sede_id)
        asis_qs = asis_qs.filter(curso__sede_id=sede_id)
        asis_det_qs = asis_det_qs.filter(asistencia__curso__sede_id=sede_id)

    if dep_id:
        est_qs = est_qs.filter(curso__disciplina_id=dep_id)
        curso_qs = curso_qs.filter(disciplina_id=dep_id)
        plan_qs = plan_qs.filter(curso__disciplina_id=dep_id)
        asis_qs = asis_qs.filter(curso__disciplina_id=dep_id)
        asis_det_qs = asis_det_qs.filter(asistencia__curso__disciplina_id=dep_id)

    # === KPI: GESTIÓN GENERAL ===
    total_estudiantes = est_qs.count()
    estudiantes_activos = est_qs.filter(activo=True).count()
    total_profesores = Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).count()
    total_cursos = curso_qs.count()
    total_sedes = curso_qs.values("sede_id").distinct().count()
    planes_total = plan_qs.count()
    planes_publicas = plan_qs.filter(publica=True).count()
    cumplimiento_planificacion = round((planes_publicas / planes_total) * 100, 1) if planes_total else 0
    tasa_participacion = round((estudiantes_activos / total_estudiantes) * 100, 1) if total_estudiantes else 0

    # === KPI: ACADÉMICO-DEPORTIVO ===
    clases_total = asis_qs.count()
    clases_realizadas = asis_qs.filter(estado=AsistenciaCurso.Estado.CERR).count()
    cumplimiento_clases_prof = round((clases_realizadas / clases_total) * 100, 1) if clases_total else 0
    total_detalles = asis_det_qs.count()
    presentes = asis_det_qs.filter(estado="P").count()
    promedio_asistencia_curso = round((presentes / total_detalles) * 100, 1) if total_detalles else 0

    # === KPI: PARTICIPACIÓN ===
    abandono = est_qs.filter(activo=False).count()
    tasa_abandono = round((abandono / total_estudiantes) * 100, 1) if total_estudiantes else 0

    # === KPI: OPERATIVO / RECURSOS ===
    ratio_estudiantes_prof = round((total_estudiantes / total_profesores), 1) if total_profesores else 0
    canceladas = 0  # No existe el campo cancelada en el modelo actual
    tasa_cancelacion = 0
    uso_recintos = round((clases_realizadas / clases_total) * 100, 1) if clases_total else 0

    # === KPI: ESTRATÉGICOS / SOCIALES ===
    comunas_activas = Sede.objects.exclude(comuna__isnull=True).values("comuna").distinct().count()
    cobertura_territorial = round((comunas_activas / 15) * 100, 1)
    mujeres = est_qs.filter(genero__iexact="F").count()
    hombres = est_qs.filter(genero__iexact="M").count()
    total_genero = mujeres + hombres
    equidad_genero = round((mujeres / total_genero) * 100, 1) if total_genero else 0
    eventos_comunitarios = 0  # el modelo Planificacion no tiene campo tipo

    # === EVOLUCIÓN MENSUAL ===
    est_mes = (
        est_qs.annotate(mes=TruncMonth("creado"))
        .values("mes").annotate(total=Count("id")).order_by("mes")
    )
    asis_mes = (
        asis_qs.annotate(mes=TruncMonth("fecha"))
        .values("mes").annotate(total=Count("id")).order_by("mes")
    )
    meses_labels = [e["mes"].strftime("%b") for e in est_mes]
    datos_estudiantes = [e["total"] for e in est_mes]
    datos_asistencia = [a["total"] for a in asis_mes]

    # === KPI PRINCIPALES (para la vista) ===
    kpi_data = [
        {"label": "Total estudiantes", "value": total_estudiantes, "icon": "fa-users", "color": "#0ea5e9"},
        {"label": "Estudiantes activos", "value": estudiantes_activos, "icon": "fa-user-check", "color": "#10b981"},
        {"label": "Profesores", "value": total_profesores, "icon": "fa-chalkboard-teacher", "color": "#6366f1"},
        {"label": "Cursos activos", "value": total_cursos, "icon": "fa-book", "color": "#84cc16"},
        {"label": "Sedes activas", "value": total_sedes, "icon": "fa-map-marker-alt", "color": "#14b8a6"},
        {"label": "Tasa participación", "value": f"{tasa_participacion}%", "icon": "fa-chart-line", "color": "#06b6d4"},
        {"label": "Cumplimiento planificación", "value": f"{cumplimiento_planificacion}%", "icon": "fa-clipboard-check", "color": "#f59e0b"},
        {"label": "Cumplimiento clases profesor", "value": f"{cumplimiento_clases_prof}%", "icon": "fa-chalkboard", "color": "#22c55e"},
        {"label": "Asistencia promedio", "value": f"{promedio_asistencia_curso}%", "icon": "fa-calendar-check", "color": "#3b82f6"},
        {"label": "Tasa abandono", "value": f"{tasa_abandono}%", "icon": "fa-user-times", "color": "#ef4444"},
        {"label": "Ratio est./prof.", "value": ratio_estudiantes_prof, "icon": "fa-balance-scale", "color": "#f59e0b"},
        {"label": "Uso recintos", "value": f"{uso_recintos}%", "icon": "fa-building", "color": "#a855f7"},
        {"label": "Cancelaciones", "value": f"{tasa_cancelacion}%", "icon": "fa-ban", "color": "#f97316"},
        {"label": "Cobertura territorial", "value": f"{cobertura_territorial}%", "icon": "fa-globe", "color": "#06b6d4"},
        {"label": "Equidad de género", "value": f"{equidad_genero}%", "icon": "fa-venus-mars", "color": "#ec4899"},
        {"label": "Eventos comunitarios", "value": eventos_comunitarios, "icon": "fa-users", "color": "#14b8a6"},
    ]

    ctx = {
        "kpi_data": kpi_data,
        "meses_labels": meses_labels,
        "datos_estudiantes": datos_estudiantes,
        "datos_asistencia": datos_asistencia,
        "anio_actual": date.today().year,
        "programa": programa,
        "sede_id": sede_id,
        "dep_id": dep_id,
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
    }
    return render(request, "core/reportes_kpi.html", ctx)


from django.shortcuts import render
from .models import AsistenciaCurso
from applications.core.models import Sede, Deporte

def reportes_kpi_inasistencias(request):
    sede_id = request.GET.get("sede")
    dep_id = request.GET.get("disciplina")
    programa = request.GET.get("programa")

    # Base de asistencias
    asistencias = AsistenciaCurso.objects.select_related("curso", "curso__sede", "curso__disciplina")

    # Filtros
    if sede_id:
        asistencias = asistencias.filter(curso__sede_id=sede_id)
    if dep_id:
        asistencias = asistencias.filter(curso__disciplina_id=dep_id)
    if programa:
        asistencias = asistencias.filter(curso__programa=programa)

    # Indicadores KPI
    total_registros = asistencias.count()
    total_inasistencias = asistencias.filter(estado="INASISTENTE").count()
    total_justificadas = asistencias.filter(estado="INASISTENTE", justificada=True).count()
    total_no_justificadas = total_inasistencias - total_justificadas

    tasa_inasistencia = round((total_inasistencias / total_registros) * 100, 1) if total_registros else 0

    kpi_inasistencias = [
        {"label": "Total de Registros de Asistencia", "value": total_registros, "icon": "fa-calendar-check"},
        {"label": "Total de Inasistencias", "value": total_inasistencias, "icon": "fa-user-xmark"},
        {"label": "Justificadas", "value": total_justificadas, "icon": "fa-file-circle-check"},
        {"label": "No Justificadas", "value": total_no_justificadas, "icon": "fa-circle-exclamation"},
        {"label": "Tasa de Inasistencia (%)", "value": tasa_inasistencia, "icon": "fa-chart-line"},
    ]

    context = {
        "kpi_inasistencias": kpi_inasistencias,
        "sedes": Sede.objects.all(),
        "disciplinas": Deporte.objects.all(),
        "sede_id": sede_id,
        "dep_id": dep_id,
        "programa": programa,
    }

    return render(request, "core/reportes_kpi_inasistencias.html", context)

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_inasistencias_export_csv(request):
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = base - timedelta(days=base.weekday())
    domingo = lunes + timedelta(days=6)

    clases = (
        Clase.objects
        .select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte")
        .filter(fecha__range=(lunes, domingo))
    )
    sede_id = request.GET.get("sede") or ""
    deporte_id = request.GET.get("disciplina") or ""
    prof_id = request.GET.get("prof") or ""
    if sede_id:
        clases = clases.filter(sede_deporte__sede_id=sede_id)
    if deporte_id:
        clases = clases.filter(sede_deporte__deporte_id=deporte_id)
    if prof_id:
        clases = clases.filter(profesor_id=prof_id)

    asist = AsistenciaAtleta.objects.filter(clase__in=clases)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="reporte_inasistencias.csv"'
    resp.write("\ufeff")
    resp.write("Actividad,Profesor,Sede,Fecha,Inscritos,Presentes,Ausentes,%Asistencia\n")
    for c in clases.order_by("fecha", "hora_inicio"):
        qs = asist.filter(clase=c)
        p = qs.filter(presente=True).count()
        a = qs.filter(presente=False).count()
        tot = p + a
        pct = round((p / tot) * 100, 1) if tot else 0
        etiqueta = getattr(c, "tema", "") or str(getattr(c.sede_deporte, "deporte", "") or "")
        prof = c.profesor.get_full_name() if getattr(c, "profesor", None) else ""
        sede = str(getattr(c.sede_deporte, "sede", "") or "")
        fecha_str = c.fecha.isoformat()
        resp.write(f'"{etiqueta}","{prof}","{sede}",{fecha_str},{tot},{p},{a},{pct}\n')
    return resp


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_inasistencias_detalle(request, clase_id: int):
    clase = get_object_or_404(
        Clase.objects.select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte"),
        pk=clase_id
    )
    semana_base = clase.fecha
    lunes = semana_base - timedelta(days=semana_base.weekday())
    domingo = lunes + timedelta(days=6)

    asist_semana = AsistenciaAtleta.objects.filter(
        atleta__isnull=False,
        clase__fecha__range=(lunes, domingo)
    ).select_related("atleta__usuario")

    registros_clase = AsistenciaAtleta.objects.filter(clase=clase).select_related("atleta__usuario")
    filas = []
    faltas_semana = asist_semana.values("atleta_id").annotate(faltas=Count("id", filter=Q(presente=False)))
    faltas_map = {r["atleta_id"]: r["faltas"] for r in faltas_semana}

    for r in registros_clase:
        at = r.atleta
        nombre = at.usuario.get_full_name() if at and at.usuario_id else "—"
        rut = getattr(at, "rut", "—")
        tel_apod = getattr(getattr(at, "apoderado", None), "telefono", "") or ""
        ult4 = AsistenciaAtleta.objects.filter(atleta=at).order_by("-clase__fecha")[:4]
        faltas_ult4 = sum(1 for x in ult4 if not x.presente)
        filas.append({
            "rut": rut,
            "nombre": nombre,
            "faltas_semana": faltas_map.get(at.id, 0),
            "faltas_ult4": faltas_ult4,
            "tel_apod": tel_apod,
            "presente": r.presente,
            "observ": r.observaciones,
        })

    return render(request, "core/reportes_kpi_asistencias.html", {
        "clase": clase,
        "lunes": lunes, "domingo": domingo,
        "filas": filas,
    })


# 🧑‍🏫 Asistencia por clase (selector)
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request):
    fecha = request.GET.get("fecha") or ""
    try:
        fecha_dt = date.fromisoformat(fecha) if fecha else None
    except ValueError:
        fecha_dt = None

    sede_id = request.GET.get("sede") or ""
    deporte_id = request.GET.get("disciplina") or ""
    clase_id = request.GET.get("clase") or ""

    clases = Clase.objects.select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte").all()
    if fecha_dt:
        clases = clases.filter(fecha=fecha_dt)
    if sede_id:
        clases = clases.filter(sede_deporte__sede_id=sede_id)
    if deporte_id:
        clases = clases.filter(sede_deporte__deporte_id=deporte_id)

    seleccionada = None
    registros = []
    if clase_id:
        seleccionada = get_object_or_404(clases, pk=clase_id)
        registros = AsistenciaAtleta.objects.filter(clase=seleccionada).select_related("atleta__usuario").order_by(
            "atleta__usuario__last_name")

    return render(request, "core/reportes_kpi_asistencias.html", {
        "fecha": fecha,
        "sede_id": sede_id,
        "deporte_id": deporte_id,
        "clase_id": int(clase_id) if clase_id else "",
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "clases": clases.order_by("-fecha", "hora_inicio"),
        "seleccionada": seleccionada,
        "registros": registros,
    })
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_inscripciones(request):
    """Vista de reporte de inscripciones por curso."""
    return render(request, "core/reportes_kpi_asistencias.html")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_calendario(request):
    """Vista del calendario consolidado de clases, citas y eventos."""
    return render(request, "core/reporte_calendario.html")


# Placeholders
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_curso(request):
    return render(request, "core/reportes_kpi_estudiantes.html", {"titulo": "Asistencia por curso (rango) – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_sede(request):
    return render(request, "core/reportes_kpi_estudiantes.html", {"titulo": "Asistencia por sede (rango) – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_llegadas_tarde(request):
    return render(request, "core/reportes_kpi_estudiantes.html", {"titulo": "Llegadas tarde – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_exportar_todo(request):
    return HttpResponse("Exportador general (xlsx/pdf) – por implementar")

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_excel(request):
    """Exporta los KPI generales a un archivo Excel."""
    data = obtener_kpi_generales()

    # Convertimos solo los datos numéricos simples
    plano = {
        "Total estudiantes": [data["total_estudiantes"]],
        "Estudiantes activos": [data["estudiantes_activos"]],
        "Total cursos": [data["total_cursos"]],
        "Total sedes": [data["total_sedes"]],
        "Cumplimiento planificación (%)": [data["cumplimiento_planificacion"]],
    }

    df = pd.DataFrame(plano)
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="reporte_kpi.xlsx"'
    df.to_excel(response, index=False)
    return response


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_pdf(request):
    data = obtener_kpi_generales()

    # Generar un gráfico simple de ejemplo (estudiantes por mes)
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun"]
    valores = [12, 18, 25, 30, 22, 35]

    fig, ax = plt.subplots()
    ax.plot(meses, valores, marker="o", linewidth=2, color="#003366")
    ax.set_title("Evolución mensual de estudiantes")
    ax.set_ylabel("Cantidad")
    ax.set_xlabel("Mes")
    buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    chart_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)

    contexto = {
        "titulo": "Reporte de Indicadores CPC",
        "kpi": [
            ("Total estudiantes", data["total_estudiantes"]),
            ("Estudiantes activos", data["estudiantes_activos"]),
            ("Total cursos", data["total_cursos"]),
            ("Total sedes", data["total_sedes"]),
            ("Cumplimiento planificación (%)", data["cumplimiento_planificacion"]),
        ],
        "chart_base64": chart_base64,
        "logo_url": request.build_absolute_uri("/static/img/logo_cpc.png"),  # ajusta el path
        "ahora": timezone.now(),
    }

    html = render_to_string("core/pdf_kpi_base.html", contexto)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="reporte_kpi.pdf"'
    return response

def obtener_kpi_generales():
    """Devuelve los datos numéricos generales usados por los reportes KPI"""
    from applications.core.models import Estudiante, Curso, Sede, Planificacion, AsistenciaCurso, AsistenciaCursoDetalle

    # Conteos generales
    total_estudiantes = Estudiante.objects.count()
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()
    total_cursos = Curso.objects.count()
    total_sedes = Sede.objects.count()
    total_planificaciones = Planificacion.objects.count()
    planif_publicas = Planificacion.objects.filter(publica=True).count()

    cumplimiento_planificacion = (
        round((planif_publicas / total_planificaciones) * 100, 1)
        if total_planificaciones > 0 else 0
    )

    # KPI mensuales (crecimiento de estudiantes)
    est_mes = (
        Estudiante.objects.annotate(mes=TruncMonth("creado"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    # KPI mensuales de asistencia (clases registradas)
    asis_mes = (
        AsistenciaCurso.objects.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    return {
        "total_estudiantes": total_estudiantes,
        "estudiantes_activos": estudiantes_activos,
        "total_cursos": total_cursos,
        "total_sedes": total_sedes,
        "cumplimiento_planificacion": cumplimiento_planificacion,
        "est_mes": list(est_mes),
        "asis_mes": list(asis_mes),
    }


# ========= Utilidades de ubicación / QR =========
def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def _nearest_sede(lat, lng):
    sedes = Sede.objects.exclude(Q(latitud__isnull=True) | Q(longitud__isnull=True))
    best, best_d = None, None
    for s in sedes:
        d = _haversine_m(lat, lng, s.latitud, s.longitud)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    try:
        from applications.profesor.models import AsistenciaProfesor
    except Exception:
        return HttpResponse("Función no disponible: falta el modelo AsistenciaProfesor.", status=501)

    ultima_entrada = (
        AsistenciaProfesor.objects
        .filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.ENTRADA)
        .order_by("-fecha", "-hora").first()
    )
    ultima_salida = (
        AsistenciaProfesor.objects
        .filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.SALIDA)
        .order_by("-fecha", "-hora").first()
    )

    mensaje, ok = None, False

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()  # 'entrada' | 'salida'
        if action not in ("entrada", "salida"):
            mensaje = "Acción inválida."
            return render(request, "profesor/mi_asistencia_qr.html", {
                "ultima_entrada": ultima_entrada, "ultima_salida": ultima_salida, "mensaje": mensaje, "ok": False
            })
        qr_text = request.POST.get("qr_text", "").strip()
        lat_str = request.POST.get("geo_lat")
        lng_str = request.POST.get("geo_lng")

        sede = None

        if qr_text.startswith("SEDE:"):
            try:
                sede_id = int(qr_text.split(":", 1)[1])
                sede = Sede.objects.filter(pk=sede_id).first()
            except ValueError:
                sede = None

        if not sede and lat_str and lng_str:
            try:
                lat, lng = float(lat_str), float(lng_str)
                sede_cerca, d_m = _nearest_sede(lat, lng)
                if sede_cerca and d_m <= (sede_cerca.radio_metros or 150):
                    sede = sede_cerca
                else:
                    mensaje = "No estás dentro del radio de una sede registrada."
            except Exception:
                mensaje = "Ubicación inválida."

        if not sede:
            mensaje = mensaje or "QR inválido o ubicación no válida."
        else:
            hoy = timezone.localdate()
            ahora = timezone.localtime().time()
            tipo = (AsistenciaProfesor.Tipo.ENTRADA if action == "entrada"
                    else AsistenciaProfesor.Tipo.SALIDA)

            ya_existe = AsistenciaProfesor.objects.filter(
                usuario=request.user, fecha=hoy, tipo=tipo
            ).exists()

            if ya_existe:
                mensaje = "Ya registraste tu entrada hoy." if tipo == AsistenciaProfesor.Tipo.ENTRADA \
                    else "Ya registraste tu salida hoy."
            else:
                AsistenciaProfesor.objects.create(
                    usuario=request.user, sede=sede, fecha=hoy, hora=ahora, tipo=tipo
                )
                ok = True
                hhmm = timezone.localtime().strftime("%H:%M")
                pref = "Entrada" if tipo == AsistenciaProfesor.Tipo.ENTRADA else "Salida"
                mensaje = f"{pref} registrada correctamente — {hhmm} en {sede.nombre}"

    return render(request, "profesor/mi_asistencia_qr.html", {
        "ultima_entrada": ultima_entrada,
        "ultima_salida": ultima_salida,
        "mensaje": mensaje,
        "ok": ok,
    })


# ====== Asistencia (visualizar alumnos del curso) ======
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def asistencia_estudiantes(request, curso_id: int):
    curso = get_object_or_404(Curso, pk=curso_id)

    # Seguridad: profesor solo ve sus cursos
    if _es_prof(request.user) and not (
        curso.profesor_id == request.user.id or curso.profesores_apoyo.filter(id=request.user.id).exists()
    ):
        return HttpResponseForbidden("No puedes ver alumnos de este curso.")

    alumnos = _estudiantes_del_curso(curso)
    rows = []
    for est in alumnos:
        if getattr(est, "usuario_id", None):
            nombre = (f"{est.usuario.first_name} {est.usuario.last_name}".strip()
                      or est.usuario.get_username())
        else:
            nombre = f"{getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}".strip() or getattr(est, "rut", "—")
        rows.append({"est": est, "nombre": nombre, "rut": getattr(est, "rut", "—")})

    return render(request, "profesor/asistencia_estudiantes.html", {"curso": curso, "rows": rows})


# ====== Tomar asistencia del día ======
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_tomar(request, curso_id: int):
    from .models import AsistenciaCurso, AsistenciaCursoDetalle
    from applications.core.models import Estudiante

    curso = get_object_or_404(Curso, pk=curso_id)

    # Seguridad: solo el profesor o apoyo pueden verla
    if _es_prof(request.user) and not (
        curso.profesor_id == request.user.id or curso.profesores_apoyo.filter(id=request.user.id).exists()
    ):
        return HttpResponseForbidden("No puedes tomar asistencia de este curso.")

    hoy = timezone.localdate()

    # 🧠 Buscar o crear la asistencia de hoy
    asistencia, creada = AsistenciaCurso.objects.get_or_create(
        curso=curso, fecha=hoy, defaults={"creado_por": request.user}
    )

    # 🧩 Siempre sincronizar los alumnos del curso
    alumnos_curso = list(Estudiante.objects.filter(curso=curso))
    existentes = set(asistencia.detalles.values_list("estudiante_id", flat=True))
    nuevos = [a for a in alumnos_curso if a.id not in existentes]

    if nuevos:
        AsistenciaCursoDetalle.objects.bulk_create([
            AsistenciaCursoDetalle(asistencia=asistencia, estudiante=a)
            for a in nuevos
        ])
        print(f"DEBUG: se agregaron {len(nuevos)} nuevos alumnos al detalle")

    # 🧾 Procesar acciones POST
    if request.method == "POST":
        accion = (request.POST.get("accion") or "").lower()

        if accion == "entrada":
            asistencia.estado = AsistenciaCurso.Estado.ENCU
            asistencia.inicio_real = timezone.localtime().time()
            asistencia.save(update_fields=["estado", "inicio_real"])
            messages.success(request, "Entrada registrada.")
            return redirect("core:asistencia_tomar", curso_id=curso.id)

        elif accion == "salida":
            asistencia.estado = AsistenciaCurso.Estado.CERR
            asistencia.fin_real = timezone.localtime().time()
            asistencia.save(update_fields=["estado", "fin_real"])
            messages.success(request, "Salida registrada.")
            return redirect("core:asistencia_tomar", curso_id=curso.id)

        elif accion == "guardar":
            for d in asistencia.detalles.all():
                estado = request.POST.get(f"estado_{d.estudiante_id}")
                obs = (request.POST.get(f"obs_{d.estudiante_id}") or "").strip()
                if estado in ("P", "A", "J"):
                    d.estado = estado
                    d.observaciones = obs
                    d.save(update_fields=["estado", "observaciones"])
            messages.success(request, "Asistencia guardada.")
            return redirect("core:asistencia_tomar", curso_id=curso.id)

    # 🧍‍♂️ Construir la lista de alumnos para la tabla
    detalles = asistencia.detalles.select_related("estudiante")
    rows = []
    for d in detalles:
        est = d.estudiante
        nombre = (
                f"{getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}".strip()
                or getattr(est, "rut", "—")
        )
        rows.append({
            "ins": d,
            "est": est,
            "nombre": nombre,
            "code": d.estado,
            "obs": d.observaciones,
        })

    print(f"DEBUG: curso={curso}, alumnos={len(rows)}")

    ctx = {
        "curso": curso,
        "clase": asistencia,
        "rows": rows,
        "resumen": asistencia.resumen,
    }
    return render(request, "profesor/asistencia_tomar.html", ctx)

# --- Compat: si tu urls antiguas apuntan a 'asistencia_profesor', redirige al tomar ---
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    return redirect("core:asistencia_tomar", curso_id=curso_id)


# ====== Ficha estudiante (stub) ======
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")


@login_required
def inscribir_en_curso(request, curso_id: int, estudiante_id: int):
    CursoModel = apps.get_model('core', 'Curso')
    EstudianteModel = apps.get_model('core', 'Estudiante')
    InscripcionCurso = apps.get_model('core', 'InscripcionCurso')

    if not (CursoModel and EstudianteModel and InscripcionCurso):
        messages.error(request, "Modelos no disponibles. Revisa INSTALLED_APPS y apps.py (label='core').")
        return redirect("/")

    curso = get_object_or_404(CursoModel, pk=curso_id)
    estudiante = get_object_or_404(EstudianteModel, pk=estudiante_id)

    try:
        _, created = InscripcionCurso.objects.get_or_create(curso=curso, estudiante=estudiante)
    except IntegrityError:
        created = False

    if created:
        messages.success(request, f"{estudiante} inscrito/a en {curso}.")
    else:
        messages.info(request, f"{estudiante} ya estaba inscrito/a en {curso}.")

    try:
        return redirect(reverse("core:curso_detalle", args=[curso.id]))
    except Exception:
        return redirect("core:cursos_list")


# ---------- Helper APODERADO ----------
def _ensure_apoderado_user(nombre_completo: str, rut: str, telefono: str = "", email: str = ""):
    if not rut:
        return None
    rut_norm = rut.strip().replace(".", "").upper()
    try:
        user, _ = Usuario.objects.get_or_create(
            rut=rut_norm,
            defaults={
                "username": rut_norm,
                "tipo_usuario": Usuario.Tipo.APOD,
                "email": email or "",
                "telefono": telefono or "",
                "password": make_password(rut_norm),
            },
        )
        if nombre_completo:
            parts = nombre_completo.strip().split()
            user.first_name = parts[0][:30] if parts else user.first_name
            user.last_name = " ".join(parts[1:])[:150] if len(parts) > 1 else user.last_name
        user.tipo_usuario = Usuario.Tipo.APOD
        if telefono and not getattr(user, "telefono", ""):
            user.telefono = telefono
        if email and not user.email:
            user.email = email
        user.save()
        return user
    except Exception:
        return None


# ---------- Rutas opcionales para crear según programa ----------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def estudiante_nuevo_selector(request):
    return render(request, "core/estudiante_nuevo_selector.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create_formativo(request):
    from django import forms
    if request.method == "POST":
        data = request.POST.copy()
        data["programa_elegido"] = "FORM"

        form = EstudianteForm(data)
        if "programa_elegido" in form.fields:
            form.fields["programa_elegido"].widget = forms.HiddenInput()

        if form.is_valid():
            est = form.save()
            _ensure_apoderado_user(
                nombre_completo=form.cleaned_data.get("apoderado_nombre", ""),
                rut=form.cleaned_data.get("apoderado_rut", ""),
                telefono=form.cleaned_data.get("apoderado_telefono", ""),
                email=form.cleaned_data.get("email", ""),
            )
            messages.success(request, "Estudiante (Formativo) registrado correctamente.")
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm(initial={"programa_elegido": "FORM"})
        if "programa_elegido" in form.fields:
            form.fields["programa_elegido"].widget = forms.HiddenInput()

    return render(request, "core/estudiante_form.html", {
        "form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:estudiantes_list"),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create_alto(request):
    from django import forms
    if request.method == "POST":
        data = request.POST.copy()
        data["programa_elegido"] = "ALTO"
        data.pop("sin_info_deportiva", None)

        form = EstudianteForm(data)
        if "programa_elegido" in form.fields:
            form.fields["programa_elegido"].widget = forms.HiddenInput()
        if "sin_info_deportiva" in form.fields:
            form.fields["sin_info_deportiva"].widget = forms.HiddenInput()

        if form.is_valid():
            est = form.save()
            if hasattr(est, "es_alto"):
                try:
                    setattr(est, "es_alto", True)
                    est.save(update_fields=["es_alto"])
                except Exception:
                    est.save()
            messages.success(request, "Estudiante (Alto rendimiento) registrado correctamente.")
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm(initial={
            "programa_elegido": "ALTO",
            "sin_info_deportiva": False,
        })
        if "programa_elegido" in form.fields:
            form.fields["programa_elegido"].widget = forms.HiddenInput()
        if "sin_info_deportiva" in form.fields:
            form.fields["sin_info_deportiva"].widget = forms.HiddenInput()

    return render(request, "core/estudiante_form.html", {
        "form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:estudiantes_list"),
    })


# ====== Solicitudes de registro público (genéricas de compatibilidad) ======
def _get_registro_publico_model():
    try:
        from .forms import RegistroPublicoForm
    except Exception:
        return None, []
    Form = RegistroPublicoForm
    Model = getattr(getattr(Form, "Meta", None), "model", None)
    if not Model:
        return None, []
    fields = [f.name for f in Model._meta.fields]
    return Model, fields


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def solicitudes_list(request):
    Model, fields = _get_registro_publico_model()
    if not Model:
        return HttpResponse("No se pudo detectar el modelo de Registro Público. Revisa RegistroPublicoForm.Meta.model.",
                            status=501)

    estado = (request.GET.get("estado") or "").strip().lower()
    qs = Model.objects.all()

    if "estado" in fields and estado:
        qs = qs.filter(estado__iexact=estado)
    elif "gestionada" in fields and estado:
        val = True if estado in ("ok", "si", "true", "1", "gestionada") else False
        qs = qs.filter(gestionada=val)

    order_field = "creado" if "creado" in fields else ("created_at" if "created_at" in fields else "-id")
    if order_field == "-id":
        qs = qs.order_by("-id")
    else:
        qs = qs.order_by(f"-{order_field}")

    return render(request, "core/solicitudes_list.html", {
        "items": qs,
        "fields": fields,
        "estado": estado,
        "has_estado": "estado" in fields,
        "has_gestionada": "gestionada" in fields,
        "order_field": order_field,
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def solicitud_detail(request, pk: int):
    Model, fields = _get_registro_publico_model()
    if not Model:
        return HttpResponse("No se pudo detectar el modelo de Registro Público.", status=501)
    obj = get_object_or_404(Model, pk=pk)
    return render(request, "core/registro_detail.html", {"obj": obj, "fields": fields})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def solicitud_marcar_gestionada(request, pk: int):
    Model, fields = _get_registro_publico_model()
    if not Model:
        return HttpResponse("No se pudo detectar el modelo de Registro Público.", status=501)
    obj = get_object_or_404(Model, pk=pk)

    updated = False
    if "gestionada" in fields:
        setattr(obj, "gestionada", True)
        updated = True
    elif "estado" in fields:
        setattr(obj, "estado", "gestionada")
        updated = True

    if updated:
        if hasattr(obj, "gestionado_por") and request.user.is_authenticated:
            try:
                obj.gestionado_por = request.user
            except Exception:
                pass
        if hasattr(obj, "actualizado_en"):
            try:
                obj.actualizado_en = timezone.now()
            except Exception:
                pass
        obj.save()
        messages.success(request, "Solicitud marcada como gestionada.")
    else:
        messages.info(request, "El modelo no tiene campo 'gestionada' ni 'estado'. No se realizaron cambios.")

    return redirect("core:registro_list")


# === Postulaciones (Registro Público) ===
def _get_postulacion_model():
    Model = apps.get_model('core', 'PostulacionEstudiante')
    if not Model:
        return None, {}
    estados_map = {key: label for key, label in getattr(Model, 'Estado').choices}
    return Model, estados_map


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def registro_list(request):
    Model, estados_map = _get_postulacion_model()
    if not Model:
        return HttpResponse("No se encontró el modelo PostulacionEstudiante.", status=501)

    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip().upper()

    qs = Model.objects.all()
    if estado in estados_map:
        qs = qs.filter(estado=estado)

    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(email__icontains=q) |
            Q(telefono__icontains=q) |
            Q(comuna__icontains=q)
        )

    order_field = "creado" if hasattr(Model, "creado") else ("modificado" if hasattr(Model, "modificado") else "id")
    qs = qs.order_by(f"-{order_field}")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    kpis = {key: Model.objects.filter(estado=key).count() for key in estados_map.keys()}
    kpis["ALL"] = Model.objects.count()

    return render(request, "core/registro_list.html", {
        "page_obj": page_obj,
        "items": page_obj,
        "q": q,
        "estado": estado,
        "estados_map": estados_map,
        "kpis": kpis,
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def registro_detail(request, pk: int):
    Model, estados_map = _get_postulacion_model()
    if not Model:
        return HttpResponse("No se encontró el modelo PostulacionEstudiante.", status=501)

    obj = get_object_or_404(Model, pk=pk)

    if request.method == "POST":
        accion = (request.POST.get("accion") or "").strip().lower()
        trans = {
            "contactada": "CON",
            "aceptada": "ACE",
            "rechazada": "REC",
            "reabrir": "NEW",
        }
        if accion in trans:
            nuevo = trans[accion]
            if obj.estado != nuevo:
                obj.estado = nuevo
                nota = (request.POST.get("nota") or "").strip()
                if nota:
                    sep = "\n" if (obj.comentarios or "").strip() else ""
                    obj.comentarios = f"{obj.comentarios or ''}{sep}[{timezone.now():%Y-%m-%d %H:%M}] {request.user.get_username()}: {nota}"
                update_fields = ["estado", "comentarios"]
                if hasattr(obj, "modificado"):
                    obj.modificado = timezone.now()
                    update_fields.append("modificado")
                obj.save(update_fields=update_fields)
                messages.success(request, f"Postulación actualizada a: {estados_map.get(nuevo, nuevo)}.")
            else:
                messages.info(request, "La postulación ya estaba en ese estado.")
        else:
            messages.error(request, "Acción inválida.")
        return redirect("core:registro_detail", pk=obj.pk)

    return render(request, "core/registro_detail.html", {
        "obj": obj,
        "estados_map": estados_map,
        "show_back": True, "back_to": _back_to_url(request, "core:registro_list"),
    })


# === ADMIN: períodos de registro ===
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def periodos_list(request):
    q = (request.GET.get("q") or "").strip()
    filtro = (request.GET.get("estado") or "").strip().upper()  # PROG | OPEN | CLOSE | ACT | INACT | ""
    qs = RegistroPeriodo.objects.all()
    if q:
        qs = qs.filter(nombre__icontains=q)
    if filtro in (RegistroPeriodo.Estado.PROGRAMADA, RegistroPeriodo.Estado.ABIERTA, RegistroPeriodo.Estado.CERRADA):
        qs = qs.filter(estado=filtro)
    elif filtro == "ACT":
        qs = qs.filter(activo=True)
    elif filtro == "INACT":
        qs = qs.filter(activo=False)

    qs = qs.order_by("-creado")
    return render(request, "core/periodos_list.html", {"items": qs, "q": q, "estado": filtro})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def periodo_create(request):
    from .forms import RegistroPeriodoForm
    form = RegistroPeriodoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Período creado.")
        return redirect("core:periodos_list")
    return render(request, "core/periodo_form.html", {
        "form": form, "is_edit": False,
        "show_back": True, "back_to": _back_to_url(request, "core:periodos_list"),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def periodo_edit(request, periodo_id: int):
    from .forms import RegistroPeriodoForm
    obj = get_object_or_404(RegistroPeriodo, pk=periodo_id)
    form = RegistroPeriodoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Período actualizado.")
        return redirect("core:periodos_list")
    return render(request, "core/periodo_form.html", {
        "form": form, "is_edit": True, "obj": obj,
        "show_back": True, "back_to": _back_to_url(request, "core:periodos_list"),
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def periodo_toggle_activo(request, periodo_id: int):
    obj = get_object_or_404(RegistroPeriodo, pk=periodo_id)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    messages.success(request, "Período activado." if obj.activo else "Período desactivado.")
    return redirect("core:periodos_list")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def periodo_set_estado(request, periodo_id: int):
    obj = get_object_or_404(RegistroPeriodo, pk=periodo_id)
    to = (request.POST.get("to") or "").upper()  # PROG | OPEN | CLOSE
    valid = {RegistroPeriodo.Estado.PROGRAMADA, RegistroPeriodo.Estado.ABIERTA, RegistroPeriodo.Estado.CERRADA}
    if to in valid:
        obj.estado = to
        obj.save(update_fields=["estado"])
        messages.success(request, f"Estado del período cambiado a: {obj.get_estado_display()}.")
    else:
        messages.error(request, "Estado inválido.")
    return redirect("core:periodos_list")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def periodo_cerrar_hoy(request, periodo_id: int):
    obj = get_object_or_404(RegistroPeriodo, pk=periodo_id)
    now = timezone.now()
    if not obj.fin or obj.fin >= now:
        obj.fin = now
        obj.estado = RegistroPeriodo.Estado.CERRADA
        obj.save(update_fields=["fin", "estado"])
        messages.success(request, "Período cerrado a partir de ahora.")
    else:
        messages.info(request, "El período ya estaba cerrado en una fecha anterior.")
    return redirect("core:periodos_list")


# ========== EXPORTAR KPI ESTUDIANTES ==========
@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_excel_estudiantes(request):
    data = obtener_kpi_estudiantes()  # función que ya usamos para los KPI
    df = pd.DataFrame(data)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="kpi_estudiantes.xlsx"'
    df.to_excel(response, index=False)
    return response


# ========== EXPORTAR KPI ASISTENCIAS ==========
@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_excel_asistencias(request):
    data = obtener_kpi_asistencias()
    df = pd.DataFrame(data)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="kpi_asistencias.xlsx"'
    df.to_excel(response, index=False)
    return response


# ========== EXPORTAR KPI PLANIFICACIONES ==========
@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_excel_planificaciones(request):
    data = obtener_kpi_planificaciones()
    df = pd.DataFrame(data)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="kpi_planificaciones.xlsx"'
    df.to_excel(response, index=False)
    return response


# ========== EXPORTAR KPI DESEMPEÑO ==========
@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_excel_desempeno(request):
    data = obtener_kpi_desempeno()
    df = pd.DataFrame(data)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="kpi_desempeno.xlsx"'
    df.to_excel(response, index=False)
    return response


# ========== EXPORTAR KPI GENERAL ==========
@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_excel_general(request):
    # Combina todos los KPI en un solo DataFrame
    data_general = {
        "Estudiantes": obtener_kpi_estudiantes(),
        "Asistencias": obtener_kpi_asistencias(),
        "Planificaciones": obtener_kpi_planificaciones(),
        "Desempeño": obtener_kpi_desempeno(),
    }

    # Crear un Excel con múltiples hojas
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="kpi_general.xlsx"'

    with pd.ExcelWriter(response, engine="openpyxl") as writer:
        for nombre, datos in data_general.items():
            df = pd.DataFrame(datos)
            df.to_excel(writer, sheet_name=nombre, index=False)

    return response

# ===== FUNCIONES KPI CON DATOS REALES =====
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from applications.core.models import Estudiante, Curso, Sede, Planificacion, AsistenciaCurso, AsistenciaCursoDetalle


def obtener_kpi_estudiantes():
    """Indicadores de estudiantes"""
    total = Estudiante.objects.count()
    activos = Estudiante.objects.filter(activo=True).count()
    inactivos = total - activos

    # Nuevos por mes
    nuevos_mes = (
        Estudiante.objects.annotate(mes=TruncMonth("creado"))
        .values("mes")
        .annotate(nuevos=Count("id"))
        .order_by("mes")
    )

    data = []
    for e in nuevos_mes:
        mes = e["mes"].strftime("%b")
        retencion = round((activos / total) * 100, 1) if total else 0
        data.append({
            "Mes": mes,
            "Nuevos": e["nuevos"],
            "Activos": activos,
            "Inactivos": inactivos,
            "Retención %": retencion,
        })
    return data


def obtener_kpi_asistencias():
    """Indicadores de asistencia"""
    total_clases = AsistenciaCurso.objects.count()
    total_registros = AsistenciaCursoDetalle.objects.count()
    presentes = AsistenciaCursoDetalle.objects.filter(estado="P").count()
    ausentes = AsistenciaCursoDetalle.objects.filter(estado="A").count()
    justificados = AsistenciaCursoDetalle.objects.filter(estado="J").count()

    tasa_asistencia = round((presentes / total_registros) * 100, 1) if total_registros else 0

    # Por mes
    por_mes = (
        AsistenciaCurso.objects.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(clases=Count("id"))
        .order_by("mes")
    )

    data = []
    for m in por_mes:
        mes = m["mes"].strftime("%b")
        data.append({
            "Mes": mes,
            "Clases registradas": m["clases"],
            "Presentes": presentes,
            "Ausentes": ausentes,
            "Justificados": justificados,
            "Tasa asistencia %": tasa_asistencia,
        })
    return data


def obtener_kpi_planificaciones():
    """Indicadores de planificación docente"""
    total = Planificacion.objects.count()
    publicadas = Planificacion.objects.filter(publica=True).count()
    cumplimiento = round((publicadas / total) * 100, 1) if total else 0

    por_mes = (
        Planificacion.objects.annotate(mes=TruncMonth("semana"))
        .values("mes")
        .annotate(planificadas=Count("id"))
        .order_by("mes")
    )

    data = []
    for p in por_mes:
        mes = p["mes"].strftime("%b")
        data.append({
            "Mes": mes,
            "Planificadas": p["planificadas"],
            "Publicadas": publicadas,
            "Cumplimiento %": cumplimiento,
        })
    return data


def obtener_kpi_desempeno():
    """Indicadores de desempeño deportivo"""
    # Si no hay campos de logros, usaremos proxies (por ejemplo, planificaciones tipo evento)
    logros_nacionales = Planificacion.objects.filter(tipo__icontains="nacional").count() if hasattr(Planificacion, "tipo") else 0
    logros_internacionales = Planificacion.objects.filter(tipo__icontains="internacional").count() if hasattr(Planificacion, "tipo") else 0

    # Evolución mensual de logros (si existen tipos)
    por_mes = (
        Planificacion.objects.filter(tipo__icontains="logro").annotate(mes=TruncMonth("semana"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    ) if hasattr(Planificacion, "tipo") else []

    data = []
    for l in por_mes:
        mes = l["mes"].strftime("%b")
        data.append({
            "Mes": mes,
            "Logros Nacionales": logros_nacionales,
            "Logros Internacionales": logros_internacionales,
        })
    if not data:
        data.append({
            "Mes": "—",
            "Logros Nacionales": logros_nacionales,
            "Logros Internacionales": logros_internacionales,
        })
    return data

@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_general(request):
    """Exporta todos los KPI en un solo PDF con formato visual."""
    data = {
        "estudiantes": obtener_kpi_estudiantes(),
        "asistencias": obtener_kpi_asistencias(),
        "planificaciones": obtener_kpi_planificaciones(),
        "desempeno": obtener_kpi_desempeno(),
        "generales": obtener_kpi_generales(),
    }

    html = render_to_string("core/reportes_pdf_general.html", data)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='reporte_general_kpi.pdf'"
    return response

@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_estudiantes(request):
    """Exporta el reporte PDF de KPI de estudiantes."""
    data = {"kpi_estudiantes": obtener_kpi_estudiantes()}

    html = render_to_string("core/reportes_pdf_estudiantes.html", data)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='kpi_estudiantes.pdf'"
    return response

@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_asistencias(request):
    """Exporta el reporte PDF de KPI de asistencias."""
    data = {"kpi_asistencias": obtener_kpi_asistencias()}

    html = render_to_string("core/reportes_pdf_asistencias.html", data)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='kpi_asistencias.pdf'"
    return response

@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_planificaciones(request):
    """Exporta el reporte PDF de KPI de planificaciones."""
    data = {"kpi_planificaciones": obtener_kpi_planificaciones()}

    html = render_to_string("core/reportes_pdf_planificaciones.html", data)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='kpi_planificaciones.pdf'"
    return response

@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_desempeno(request):
    """Exporta el reporte PDF de KPI de desempeño."""
    data = {"kpi_desempeno": obtener_kpi_desempeno()}

    html = render_to_string("core/reportes_pdf_desempeno.html", data)
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='kpi_desempeno.pdf'"
    return response

def reportes_kpi_estudiantes(request):
    programa = request.GET.get("programa", "").strip()

    # Filtrar estudiantes por programa (si corresponde)
    estudiantes = Estudiante.objects.all()
    if programa:
        estudiantes = estudiantes.filter(curso__programa=programa)

    # Indicadores base
    total_estudiantes = estudiantes.count()
    activos = estudiantes.filter(activo=True).count()
    nuevos = estudiantes.filter(creado__year=2025).count()  # ejemplo: ajustar año dinámico
    retencion = 0
    if total_estudiantes:
        retencion = round((activos / total_estudiantes) * 100, 1)

    kpi_estudiantes = [
        {"label": "Total de Estudiantes", "value": total_estudiantes, "icon": "fa-users"},
        {"label": "Estudiantes Activos", "value": activos, "icon": "fa-user-check"},
        {"label": "Nuevos este año", "value": nuevos, "icon": "fa-user-plus"},
        {"label": "Tasa de Retención (%)", "value": f"{retencion}%", "icon": "fa-chart-line"},
    ]

    return render(request, "core/reportes_kpi_estudiantes.html", {
        "kpi_estudiantes": kpi_estudiantes,
        "programa": programa,
    })

def reportes_kpi_planificaciones(request):
    profesor_id = request.GET.get("profesor")

    planificaciones = Planificacion.objects.all()
    if profesor_id:
        planificaciones = planificaciones.filter(autor_id=profesor_id)

    total = planificaciones.count()
    publicadas = planificaciones.filter(publica=True).count()

    cumplimiento = 0
    if total:
        cumplimiento = round((publicadas / total) * 100, 1)

    kpi_planificaciones = [
        {"label": "Total de Planificaciones", "value": total, "icon": "fa-clipboard-list"},
        {"label": "Publicadas", "value": publicadas, "icon": "fa-paper-plane"},
        {"label": "Cumplimiento (%)", "value": f"{cumplimiento}%", "icon": "fa-bullseye"},
    ]

    return render(request, "core/reportes_kpi_planificaciones.html", {
        "kpi_planificaciones": kpi_planificaciones,
        "profesores": Usuario.objects.filter(tipo_usuario="PROF"),
        "profesor_id": profesor_id,
    })

def reportes_kpi_desempeno(request):
    dep_id = request.GET.get("disciplina")

    estudiantes = Estudiante.objects.all()
    if dep_id:
        estudiantes = estudiantes.filter(curso__disciplina_id=dep_id)

    logros_nac = estudiantes.filter(logro_nacional=True).count()
    logros_int = estudiantes.filter(logro_internacional=True).count()
    total = estudiantes.count()

    porc_logros = 0
    if total:
        porc_logros = round(((logros_nac + logros_int) / total) * 100, 1)

    kpi_desempeno = [
        {"label": "Logros Nacionales", "value": logros_nac, "icon": "fa-medal"},
        {"label": "Logros Internacionales", "value": logros_int, "icon": "fa-earth-americas"},
        {"label": "Porcentaje con Logros", "value": f"{porc_logros}%", "icon": "fa-chart-pie"},
    ]

    return render(request, "core/reportes_kpi_desempeno.html", {
        "kpi_desempeno": kpi_desempeno,
        "disciplinas": Deporte.objects.all(),
        "dep_id": dep_id,
    })

def reportes_kpi_asistencias(request):
    sede_id = request.GET.get("sede")
    dep_id = request.GET.get("disciplina")

    asistencias = AsistenciaCurso.objects.select_related("curso")

    # Aplicar filtros
    if sede_id:
        asistencias = asistencias.filter(curso__sede_id=sede_id)
    if dep_id:
        asistencias = asistencias.filter(curso__disciplina_id=dep_id)

    total_asistencias = asistencias.count()
    cursos_con_asistencia = asistencias.values("curso").distinct().count()

    promedio = 0
    if cursos_con_asistencia:
        promedio = round(total_asistencias / cursos_con_asistencia, 1)

    kpi_asistencias = [
        {"label": "Total de Asistencias Registradas", "value": total_asistencias, "icon": "fa-calendar-check"},
        {"label": "Cursos con Asistencias", "value": cursos_con_asistencia, "icon": "fa-chalkboard-teacher"},
        {"label": "Promedio de Asistencia por Curso", "value": promedio, "icon": "fa-chart-bar"},
    ]

    return render(request, "core/reportes_kpi_asistencias.html", {
        "kpi_asistencias": kpi_asistencias,
        "sedes": Sede.objects.all(),
        "disciplinas": Deporte.objects.all(),
        "sede_id": sede_id,
        "dep_id": dep_id,
    })

def exportar_kpi_inasistencias(request):
    # Aquí generas el PDF o Excel de inasistencias
    # Por ahora, algo simple para que no falle:
    from django.http import HttpResponse
    return HttpResponse("Exportar KPI de Inasistencias (PDF)")

from django.http import HttpResponse
from django.shortcuts import render
from .models import AsistenciaCursoDetalle


def reportes_kpi_inasistencias(request):
    """Vista para mostrar los KPI de inasistencias (pantalla web)."""
    total_inasistencias = AsistenciaCursoDetalle.objects.filter(estado="A").count()
    justificadas = AsistenciaCursoDetalle.objects.filter(estado="J").count()
    injustificadas = total_inasistencias - justificadas

    kpi_inasistencias = [
        {"label": "Inasistencias Totales", "value": total_inasistencias, "icon": "fa-calendar-xmark"},
        {"label": "Justificadas", "value": justificadas, "icon": "fa-file-circle-check"},
        {"label": "No Justificadas", "value": injustificadas, "icon": "fa-file-circle-xmark"},
    ]

    return render(request, "core/reportes_kpi_inasistencias.html", {
        "kpi_inasistencias": kpi_inasistencias
    })


def exportar_kpi_inasistencias(request):
    """Exportación PDF (simplificada temporalmente)."""
    return HttpResponse("Exportar KPI de Inasistencias (PDF pendiente de implementar)")


def exportar_excel_inasistencias(request):
    """Exportación Excel (simplificada temporalmente)."""
    return HttpResponse("Exportar KPI de Inasistencias (Excel pendiente de implementar)")


# applications/core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from .models import AsistenciaCursoDetalle, AsistenciaCurso, Estudiante

def es_admin_o_coord(user):
    """Restringe el acceso solo a administradores o coordinadores."""
    return user.is_superuser or user.is_staff or user.groups.filter(name__in=["Coordinador"]).exists()


@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def asistencia_semaforo(request):
    """
    Muestra listado de estudiantes con color según faltas consecutivas.
    """
    estudiantes = Estudiante.objects.filter(asistencias_curso__isnull=False).distinct()

    data = []
    for est in estudiantes:
        registros = (
            AsistenciaCursoDetalle.objects
            .filter(estudiante=est)
            .select_related("asistencia")
            .order_by("asistencia__fecha")
        )

        faltas_consec = 0
        max_faltas = 0
        for r in registros:
            if r.estado == "A":
                faltas_consec += 1
                max_faltas = max(max_faltas, faltas_consec)
            else:
                faltas_consec = 0

        if max_faltas >= 3:
            color = "rojo"
        elif max_faltas == 2:
            color = "amarillo"
        else:
            color = "verde"

        data.append({
            "estudiante": est,
            "curso": est.curso,
            "faltas_consec": max_faltas,
            "color": color,
        })

    context = {"data": data}
    return render(request, "core/semaforo_asistencia.html", context)


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Estudiante

def estudiante_activar(request, estudiante_id):
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    estudiante.activo = True
    estudiante.save()
    messages.success(request, f"✅ El estudiante {estudiante.nombres} {estudiante.apellidos} fue activado correctamente.")
    return redirect('core:estudiantes_list')

def estudiante_desactivar(request, estudiante_id):
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    estudiante.activo = False
    estudiante.save()
    messages.warning(request, f"⚠️ El estudiante {estudiante.nombres} {estudiante.apellidos} fue desactivado correctamente.")
    return redirect('core:estudiantes_list')

