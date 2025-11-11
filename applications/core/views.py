# applications/core/views.py

import os
import base64
from io import BytesIO
from datetime import date, timedelta
from math import radians, sin, cos, asin, sqrt

import matplotlib.pyplot as plt
import pandas as pd

import re
from weasyprint import HTML
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncMonth, TruncDay
from django.http import HttpResponse, FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario, Profesor
from applications.atleta.models import Clase, AsistenciaAtleta

# ⬇️ MODELOS de core (solo una vez y solo modelos)
from applications.core.models import (
    Comunicado,              # modelo
    Curso, Sede, Estudiante,
    Deporte, Planificacion, PlanificacionVersion,
    Noticia, RegistroPeriodo,
    AsistenciaCurso, AsistenciaCursoDetalle,
)

from .forms import (
    DeporteForm,
    PlanificacionUploadForm,
    ComunicadoForm,
    NoticiaForm,
    EstudianteForm,
)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _es_prof(user) -> bool:
    return getattr(user, "tipo_usuario", None) == Usuario.Tipo.PROF


def _is_admin_or_coord(user) -> bool:
    return getattr(user, "tipo_usuario", None) in (Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)


def _periodo_abierto():

    now = timezone.now()
    qs = RegistroPeriodo.objects.filter(
        activo=True,
        estado=RegistroPeriodo.Estado.ABIERTA,
    )
    qs = qs.filter(Q(inicio__isnull=True) | Q(inicio__lte=now))
    qs = qs.filter(Q(fin__isnull=True) | Q(fin__gte=now))
    return qs.order_by("-creado").first()



def _back_to_url(request, fallback_name: str) -> str:
    nxt = (request.GET.get("next") or "").strip()
    if nxt:
        return nxt
    ref = (request.META.get("HTTP_REFERER") or "").strip()
    if ref:
        return ref
    try:
        return reverse(fallback_name)
    except Exception:
        return fallback_name

def _estudiantes_del_curso(curso):

    EstudianteModel = apps.get_model('core', 'Estudiante')


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


def es_admin_o_coord(user):

    return user.is_superuser or user.is_staff or user.groups.filter(name__in=["Coordinador"]).exists()


@login_required
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def asistencia_semaforo(request):

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



@require_http_methods(["GET"])
def home(request):
    # Noticias (tal como ya lo tienes)
    noticias_slider = (
        Noticia.objects.filter(publicada=True)
        .exclude(imagen="").exclude(imagen__isnull=True)
        .order_by("-publicada_en", "-creado")[:6]
    )
    noticias = (
        Noticia.objects.filter(publicada=True)
        .order_by("-publicada_en", "-creado")[:6]
    )

    # 👇 NUEVO: comunicados públicos (últimos 4)
    try:
        comunicados_publicos = list(Comunicado.objects.publics().order_by("-creado")[:4])
    except Exception:
        comunicados_publicos = []

    return render(
        request,
        "core/home.html",
        {
            "noticias_slider": noticias_slider,
            "noticias": noticias,
            "comunicados_publicos": comunicados_publicos,  # 👈 pasa al template
        },
    )


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



@role_required(Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def estudiantes_list_prof(request):
    q = (request.GET.get("q") or "").strip()

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

# applications/core/views.py
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import Estudiante, AsistenciaCursoDetalle


try:
    from applications.pmul.models import Cita, FichaClinica
    _PMUL_OK = True
except Exception:
    Cita = FichaClinica = None
    _PMUL_OK = False


def _estudiante_detail_context(pk: int):
    est = (
        Estudiante.objects
        .select_related("curso", "curso__sede", "curso__disciplina", "curso__profesor")
        .prefetch_related("curso__horarios")
        .get(pk=pk)
    )

    acd_qs = (
        AsistenciaCursoDetalle.objects
        .select_related("asistencia", "asistencia__curso", "asistencia__curso__sede")
        .filter(estudiante_id=pk)
        .order_by("-asistencia__fecha", "-id")
    )

    total_registros   = acd_qs.count()
    presentes         = acd_qs.filter(estado="P").count()
    total_inasist     = acd_qs.filter(estado__in=["A", "J"]).count()
    justificadas      = acd_qs.filter(estado="J").count()
    injustificadas    = max(total_inasist - justificadas, 0)
    ult_asistencias   = list(acd_qs[:20])

    proximas_citas = []
    ult_fichas     = []
    if _PMUL_OK:
        ahora = timezone.now()
        proximas_citas = (
            Cita.objects
            .select_related("profesional")
            .filter(paciente_id=pk, inicio__gte=ahora, estado__in=["PEND", "REPROG"])
            .order_by("inicio")[:5]
        )
        ult_fichas = (
            FichaClinica.objects
            .select_related("profesional")
            .filter(paciente_id=pk)
            .order_by("-fecha")[:10]
        )

    return {
        "e": est,
        "ult_asistencias": ult_asistencias,
        "kpi_total": total_registros,
        "kpi_presentes": presentes,
        "kpi_inasist": total_inasist,
        "kpi_justif": justificadas,
        "kpi_injustif": injustificadas,
        "pmul_ok": _PMUL_OK,
        "proximas_citas": proximas_citas,
        "ult_fichas": ult_fichas,
    }


def estudiante_detail(request, pk):
    ctx = _estudiante_detail_context(pk)
    return render(request, "core/estudiante_detail.html", ctx)


from io import BytesIO


def estudiante_detail_pdf(request, pk):
    ctx = _estudiante_detail_context(pk)

    html_string = render_to_string("core/estudiante_detail_pdf.html", {**ctx, "request": request})
    pdf_io = BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf(pdf_io)
    pdf_io.seek(0)

    filename_rut = (ctx["e"].rut or f"est_{ctx['e'].id}").replace(".", "").replace("-", "")
    return HttpResponse(
        pdf_io.getvalue(),
        content_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="detalle_{filename_rut}.pdf"'},
    )


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
    from django.db import transaction
    from django.contrib import messages
    from django.core.exceptions import ValidationError
    from .forms import CursoForm, CursoHorarioFormSet
    from applications.core.models import CursoHorario

    if request.method == "POST":
        form = CursoForm(request.POST)
        formset = CursoHorarioFormSet(request.POST, prefix="horarios")  # mantener visible ante errores

        if form.is_valid() and formset.is_valid():
            curso = form.save(commit=False)


            profesor = curso.profesor
            sede = curso.sede

            conflictos = []
            internos_por_dia = {}  # {dia: [(ini, fin), ...]}
            hay_horarios_validos = False

            for f in formset.cleaned_data:
                if not f or f.get("DELETE", False):
                    continue

                dia = f.get("dia")
                hora_inicio = f.get("hora_inicio")
                hora_fin = f.get("hora_fin")

                # Requisitos mínimos
                if not (dia and hora_inicio and hora_fin):
                    conflictos.append("Hay un horario incompleto (día/horas faltantes).")
                    continue

                # Orden lógico horas
                if not (hora_inicio < hora_fin):
                    conflictos.append(
                        f"El horario {CursoHorario.Dia(dia).label} debe tener hora de inicio menor a la de término."
                    )
                    continue

                hay_horarios_validos = True


                bucket = internos_por_dia.setdefault(dia, [])
                for (ini, fin) in bucket:

                    if ini < hora_fin and fin > hora_inicio:
                        conflictos.append(
                            f"Hay traslape interno el {CursoHorario.Dia(dia).label}: "
                            f"{ini.strftime('%H:%M')}–{fin.strftime('%H:%M')} con "
                            f"{hora_inicio.strftime('%H:%M')}–{hora_fin.strftime('%H:%M')}."
                        )
                        break
                bucket.append((hora_inicio, hora_fin))


                if profesor:
                    choques_prof = CursoHorario.objects.filter(
                        curso__profesor=profesor,
                        dia=dia,
                        hora_inicio__lt=hora_fin,
                        hora_fin__gt=hora_inicio,
                    )
                    if choques_prof.exists():
                        conflictos.append(
                            f"El profesor {profesor} ya tiene otro curso el "
                            f"{CursoHorario.Dia(dia).label} entre {hora_inicio} y {hora_fin}."
                        )

                if sede:
                    choques_sede = CursoHorario.objects.filter(
                        curso__sede=sede,
                        dia=dia,
                        hora_inicio__lt=hora_fin,
                        hora_fin__gt=hora_inicio,
                    )
                    if choques_sede.exists():
                        conflictos.append(
                            f"La sede {sede} ya tiene otro curso el "
                            f"{CursoHorario.Dia(dia).label} entre {hora_inicio} y {hora_fin}."
                        )

            if not hay_horarios_validos:
                conflictos.append("Debes ingresar al menos un horario válido para el curso.")

            if conflictos:
                for c in conflictos:
                    messages.error(request, f"⚠️ {c}")

                return render(request, "core/curso_form.html", {
                    "form": form,
                    "formset": formset,
                    "is_edit": False,
                    "show_back": True,
                    "back_to": _back_to_url(request, "core:cursos_list"),
                })


            with transaction.atomic():
                curso.save()
                formset.instance = curso
                formset.save()

            messages.success(request, "✅ Curso creado correctamente.")
            return redirect("core:cursos_list")

        else:
            # Mostrar errores de ambos formularios
            if not form.is_valid():
                messages.error(request, "⚠️ Error en el formulario principal del curso.")
            if not formset.is_valid():
                messages.error(request, "⚠️ Error en los horarios del curso.")

    else:
        form = CursoForm()
        formset = CursoHorarioFormSet(prefix="horarios")

    return render(request, "core/curso_form.html", {
        "form": form,
        "formset": formset,
        "is_edit": False,
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



def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

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


    def _f(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    lat0 = _f(request.GET.get("lat"))
    lng0 = _f(request.GET.get("lng"))

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

    comunas = (
        Sede.objects.exclude(comuna="")
        .values_list("comuna", flat=True).distinct().order_by("comuna")
    )

    # --- NUEVO: mapa de distancias por id (para usar en el template) ---
    distances = {}
    nearest = None
    nearest_d = None
    if lat0 is not None and lng0 is not None:
        for s in qs.exclude(latitud__isnull=True).exclude(longitud__isnull=True):
            d = _haversine_m(lat0, lng0, s.latitud, s.longitud)
            distances[s.id] = d
            if nearest_d is None or d < nearest_d:
                nearest, nearest_d = s, d

    return render(request, "core/sedes_list.html", {
        "sedes": qs,
        "q": q,
        "comuna_sel": comuna,
        "estado_sel": estado,
        "cap_cmp": cap_cmp,
        "cap_val": cap_val or "",
        "comunas": comunas,
        # --- NUEVO contexto geo ---
        "lat": lat0, "lng": lng0,
        "distances": distances,      # dict {sede_id: metros}
        "nearest": nearest,          # Sede más cercana (opcional)
        "nearest_d": nearest_d,      # distancia en metros (opcional)
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def sede_detail(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)

    # --- NUEVO: si pasas lat/lng por GET, calcula distancia a esta sede ---
    def _f(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    lat0 = _f(request.GET.get("lat"))
    lng0 = _f(request.GET.get("lng"))
    dist_m = None
    if lat0 is not None and lng0 is not None and sede.latitud is not None and sede.longitud is not None:
        dist_m = _haversine_m(lat0, lng0, sede.latitud, sede.longitud)

    return render(request, "core/sede_detail.html", {
        "sede": sede,
        "lat": lat0, "lng": lng0,   # para mostrar lo que llegó
        "dist_m": dist_m,           # metros hasta esta sede (si hubo lat/lng)
    })


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



@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def asistencia_estudiantes(request, curso_id: int):
    from .models import AsistenciaCurso, AsistenciaCursoDetalle  # ajusta import si ya los tienes arriba

    curso = get_object_or_404(Curso, pk=curso_id)


    if _es_prof(request.user) and not (
        curso.profesor_id == request.user.id or curso.profesores_apoyo.filter(id=request.user.id).exists()
    ):
        return HttpResponseForbidden("No puedes ver alumnos de este curso.")


    ultima = (
        AsistenciaCurso.objects
        .filter(curso=curso)
        .order_by("-fecha")
        .first()
    )


    detalles_map = {}
    resumen = {"P": 0, "A": 0, "J": 0, "total": 0}
    if ultima:
        qs_det = (AsistenciaCursoDetalle.objects
                  .select_related("estudiante")
                  .filter(asistencia=ultima))
        for d in qs_det:
            detalles_map[d.estudiante_id] = d
            resumen["total"] += 1
            if d.estado in ("P", "A", "J"):
                resumen[d.estado] += 1


    alumnos = _estudiantes_del_curso(curso)
    rows = []
    for est in alumnos:
        if getattr(est, "usuario_id", None):
            nombre = (f"{est.usuario.first_name} {est.usuario.last_name}".strip()
                      or est.usuario.get_username())
        else:
            nombre = (f"{getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}".strip()
                      or getattr(est, "rut", "—"))

        det = detalles_map.get(est.id)
        rows.append({
            "est": est,
            "nombre": nombre,
            "rut": getattr(est, "rut", "—"),
            "estado": getattr(det, "estado", ""),               # "", "P", "A", "J"
            "observaciones": getattr(det, "observaciones", ""), # puede ser ""
        })

    ctx = {
        "curso": curso,
        "rows": rows,
        "ultima": ultima,
        "resumen": resumen if ultima else None,
    }
    return render(request, "profesor/asistencia_estudiantes.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_tomar(request, curso_id: int):
    from .models import AsistenciaCurso, AsistenciaCursoDetalle
    from applications.core.models import Estudiante

    curso = get_object_or_404(Curso, pk=curso_id)


    if _es_prof(request.user) and not (
        curso.profesor_id == request.user.id or curso.profesores_apoyo.filter(id=request.user.id).exists()
    ):
        return HttpResponseForbidden("No puedes tomar asistencia de este curso.")

    hoy = timezone.localdate()

    # Buscar o crear la asistencia de hoy
    asistencia, creada = AsistenciaCurso.objects.get_or_create(
        curso=curso, fecha=hoy, defaults={"creado_por": request.user}
    )

    # Sincronizar alumnos del curso -> crear detalles faltantes
    alumnos_curso = list(Estudiante.objects.filter(curso=curso))
    existentes = set(asistencia.detalles.values_list("estudiante_id", flat=True))
    nuevos = [a for a in alumnos_curso if a.id not in existentes]
    if nuevos:
        AsistenciaCursoDetalle.objects.bulk_create([
            AsistenciaCursoDetalle(asistencia=asistencia, estudiante=a)
            for a in nuevos
        ])

    # POST
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
            actualizados = 0
            for d in asistencia.detalles.all():
                estado = request.POST.get(f"estado_{d.id}")
                obs = (request.POST.get(f"obs_{d.id}") or "").strip()
                if estado in ("P", "A", "J") and (d.estado != estado or (d.observaciones or "") != obs):
                    d.estado = estado
                    d.observaciones = obs
                    d.save(update_fields=["estado", "observaciones"])
                    actualizados += 1
            messages.success(request, f"Asistencia guardada. Registros actualizados: {actualizados}.")
            # 👉 Al guardar, volver al listado
            return redirect("profesor:asistencia_profesor")

        # (opcional) acción desconocida
        messages.info(request, "Acción no reconocida.")
        return redirect("core:asistencia_tomar", curso_id=curso.id)

    # Construir filas para el template
    detalles = asistencia.detalles.select_related("estudiante").order_by(
        "estudiante__apellidos", "estudiante__nombres"
    )
    rows = []
    for d in detalles:
        est = d.estudiante
        nombre = (f"{getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}".strip()
                  or getattr(est, "rut", "—"))
        rows.append({
            "ins": d,
            "est": est,
            "nombre": nombre,
            "code": d.estado,
            "obs": d.observaciones,
        })

    ctx = {
        "curso": curso,
        "clase": asistencia,
        "rows": rows,
        "resumen": getattr(asistencia, "resumen", {"P": 0, "A": 0, "J": 0, "total": len(rows)}),
    }
    return render(request, "profesor/asistencia_tomar.html", ctx)

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    return redirect("core:asistencia_tomar", curso_id=curso_id)



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



def _get_postulacion_model():
    Model = apps.get_model('core', 'PostulacionEstudiante')
    if not Model:
        return None, {}
    estados_map = {key: label for key, label in getattr(Model, 'Estado').choices}
    return Model, estados_map

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def registro_list(request):
    Model, estados_map = _get_postulacion_model()
    if not Model:
        return HttpResponse("No se encontró el modelo PostulacionEstudiante.", status=501)

    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip().upper()

    # per_page seguro (mín 1, máx 200)
    try:
        per_page = int(request.GET.get("per_page") or 25)
        if per_page < 1:
            per_page = 25
        if per_page > 200:
            per_page = 200
    except Exception:
        per_page = 25


    qs = Model.objects.all().select_related("periodo", "deporte_interes", "sede_interes")


    if estado and estado != "ALL" and estado in estados_map:
        qs = qs.filter(estado=estado)

    # Búsqueda
    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(email__icontains=q) |
            Q(telefono__icontains=q) |
            Q(comuna__icontains=q)
        )

    # Campo de orden robusto
    def _has_field(m, name: str) -> bool:
        try:
            m._meta.get_field(name)
            return True
        except Exception:
            return False

    if _has_field(Model, "creado"):
        order_field = "creado"
    elif _has_field(Model, "modificado"):
        order_field = "modificado"
    else:
        order_field = "id"

    qs = qs.order_by(f"-{order_field}")

    # Paginación
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page") or 1)


    kpis = {code: Model.objects.filter(estado=code).count() for code in estados_map.keys()}
    kpis["ALL"] = sum(kpis.values())

    return render(request, "core/registro_list.html", {
        "page_obj": page_obj,
        "items": page_obj,   # compat con tu template
        "q": q,
        "estado": estado,
        "estados_map": estados_map,
        "kpis": kpis,
        "per_page": per_page,
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
            "aceptada":  "ACE",
            "rechazada": "REC",
            "reabrir":   "NEW",
        }
        if accion in trans:
            nuevo = trans[accion]

            # Actualiza estado y comentarios (si cambió)
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

            # ✅ Al aceptar, crear/actualizar Estudiante y luego redirigir a historial
            if nuevo == "ACE":
                try:
                    from applications.core.services import crear_estudiante_desde_postulacion
                    est, creado = crear_estudiante_desde_postulacion(obj)
                    if creado:
                        messages.success(request, f"Estudiante creado: {getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}.")
                    else:
                        messages.info(request, f"Estudiante actualizado: {getattr(est, 'nombres', '')} {getattr(est, 'apellidos', '')}.")
                except Exception as e:
                    messages.warning(request, f"Postulación aceptada, pero no se pudo crear/actualizar el estudiante: {e}")

                next_url = request.GET.get("next") or request.POST.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect("/postulaciones/?estado=ACE")  # fallback sin reverse

            # Otras acciones: permanecer en el detalle
            return redirect("core:registro_detail", pk=obj.pk)

        messages.error(request, "Acción inválida.")
        return redirect("core:registro_detail", pk=obj.pk)

    return render(request, "core/registro_detail.html", {
        "obj": obj,
        "estados_map": estados_map,
        "show_back": True,
        "back_to": _back_to_url(request, "core:registro_list"),
    })


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


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def asistencia_listado_por_curso(request):


    cursos_qs = Curso.objects.all()
    if getattr(request.user, "tipo_usuario", "") == Usuario.Tipo.PROF:
        cursos_qs = cursos_qs.filter(
            Q(profesor=request.user) | Q(profesores_apoyo=request.user)
        ).distinct()

    cursos = list(
        cursos_qs.select_related("sede", "disciplina").order_by("nombre")
    )
    if not cursos:
        return render(request, "profesor/asistencia_listado.html", {"cursos": []})

    # 2) Última asistencia por curso (una por curso)
    curso_ids = [c.id for c in cursos]
    asistencias = (
        AsistenciaCurso.objects
        .filter(curso_id__in=curso_ids)
        .select_related("curso")
        .order_by("curso_id", "-fecha")
    )

    ultima_por_curso = {}
    for a in asistencias:
        if a.curso_id not in ultima_por_curso:
            ultima_por_curso[a.curso_id] = a


    ultima_ids = [a.id for a in ultima_por_curso.values()]
    detalles = (
        AsistenciaCursoDetalle.objects
        .filter(asistencia_id__in=ultima_ids)
        .select_related("estudiante")
        .order_by("estudiante__apellidos", "estudiante__nombres")
    )

    det_map = {}
    for d in detalles:
        det_map.setdefault(d.asistencia_id, []).append(d)


    for c in cursos:
        a = ultima_por_curso.get(c.id)
        c.ultima = a
        c.ultima_detalles = det_map.get(a.id, []) if a else []

    return render(request, "profesor/asistencia_listado.html", {"cursos": cursos})



from datetime import date, datetime, timedelta
from calendar import monthrange
import json

import pandas as pd
from weasyprint import HTML

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Count, F
from django.db.models.functions import TruncMonth, TruncDay
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario
from applications.core.models import (
    Estudiante, Curso, Sede, Deporte, Planificacion,
    AsistenciaCurso, AsistenciaCursoDetalle
)

ASIS_P, ASIS_A, ASIS_J = "P", "A", "J"


# --------- helpers ----------
def _to_date(v):

    try:
        return v.date() if isinstance(v, datetime) else v
    except Exception:
        return v

def _sf(qs, **kwargs):

    try:
        return qs.filter(**kwargs)
    except Exception:
        return qs

def _first_existing_field(model_cls, candidates):

    names = {f.name for f in model_cls._meta.get_fields()}
    for c in candidates:
        if c in names:
            return c
    return None

def _week_range(semana_str: str):

    try:
        base = date.fromisoformat(semana_str) if semana_str else timezone.localdate()
    except ValueError:
        base = timezone.localdate()
    lunes = base - timedelta(days=base.weekday())  # 0=lunes
    domingo = lunes + timedelta(days=6)
    return lunes, domingo

def _month_range(mes_str: str):

    today = timezone.localdate()
    if not mes_str:
        y, m = today.year, today.month
    else:
        try:
            y, m = map(int, mes_str.split("-"))
        except Exception:
            y, m = today.year, today.month
    last_day = monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last_day), y, m

def _year_range(anio_str: str):

    today = timezone.localdate()
    try:
        y = int(anio_str) if anio_str else today.year
    except Exception:
        y = today.year
    return date(y, 1, 1), date(y, 12, 31), y

def _serie_meses_completos(inicio: date, fin: date):

    items, y, m = [], inicio.year, inicio.month
    while True:
        items.append(date(y, m, 1))
        if y == fin.year and m == fin.month:
            break
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return items

def _aplicar_filtros_basicos(est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs,
                             programa: str, sede_id: str, dep_id: str):
    if programa:
        est_qs      = _sf(est_qs,      curso__programa__icontains=programa)
        curso_qs    = _sf(curso_qs,    programa__icontains=programa)
        plan_qs     = _sf(plan_qs,     curso__programa__icontains=programa)
        asis_qs     = _sf(asis_qs,     curso__programa__icontains=programa)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__programa__icontains=programa)
    if sede_id:
        est_qs      = _sf(est_qs,      curso__sede_id=sede_id)
        curso_qs    = _sf(curso_qs,    sede_id=sede_id)
        plan_qs     = _sf(plan_qs,     curso__sede_id=sede_id)
        asis_qs     = _sf(asis_qs,     curso__sede_id=sede_id)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__sede_id=sede_id)
    if dep_id:
        est_qs      = _sf(est_qs,      curso__disciplina_id=dep_id)
        curso_qs    = _sf(curso_qs,    disciplina_id=dep_id)
        plan_qs     = _sf(plan_qs,     curso__disciplina_id=dep_id)
        asis_qs     = _sf(asis_qs,     curso__disciplina_id=dep_id)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__disciplina_id=dep_id)
    return est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs

# Serializador JSON seguro para pasar listas/dicts al template
def _j(x):
    return json.dumps(x, ensure_ascii=False, cls=DjangoJSONEncoder)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def dashboard_kpi(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""
    anio_actual = timezone.now().year
    __dbg = request.GET.get("__dbg") == "1"

    est_fecha_field = _first_existing_field(Estudiante, [
        "creado","fecha_creacion","created_at","created","fecha_registro","fecha","inscrito_en","registrado_en"
    ]) or "id"

    asis_fecha_field = _first_existing_field(AsistenciaCurso, [
        "fecha","creado","fecha_creacion","created_at","created"
    ]) or "fecha"

    # QS base (con filtros)
    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.select_related("sede","profesor","disciplina")
    plan_qs  = Planificacion.objects.select_related("curso","curso__sede","curso__profesor","curso__disciplina")
    asis_qs  = AsistenciaCurso.objects.select_related("curso","curso__sede","curso__disciplina")
    asis_det_qs = AsistenciaCursoDetalle.objects.select_related("asistencia","asistencia__curso")

    # Filtros
    if programa:
        est_qs      = _sf(est_qs,      curso__programa__icontains=programa)
        curso_qs    = _sf(curso_qs,    programa__icontains=programa)
        plan_qs     = _sf(plan_qs,     curso__programa__icontains=programa)
        asis_qs     = _sf(asis_qs,     curso__programa__icontains=programa)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__programa__icontains=programa)
    if sede_id:
        est_qs      = _sf(est_qs,      curso__sede_id=sede_id)
        curso_qs    = _sf(curso_qs,    sede_id=sede_id)
        plan_qs     = _sf(plan_qs,     curso__sede_id=sede_id)
        asis_qs     = _sf(asis_qs,     curso__sede_id=sede_id)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__sede_id=sede_id)
    if dep_id:
        est_qs      = _sf(est_qs,      curso__disciplina_id=dep_id)
        curso_qs    = _sf(curso_qs,    disciplina_id=dep_id)
        plan_qs     = _sf(plan_qs,     curso__disciplina_id=dep_id)
        asis_qs     = _sf(asis_qs,     curso__disciplina_id=dep_id)
        asis_det_qs = _sf(asis_det_qs, asistencia__curso__disciplina_id=dep_id)

    # ---- MÉTRICAS CON FILTROS
    def _metricas(_est, _curso, _plan, _asis, _det):
        total_estudiantes = _est.count()
        activos           = _sf(_est, activo=True).count()
        total_profesores  = Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).count()
        total_cursos      = _curso.count()

        total_plan = _plan.count()
        plan_publicas = _sf(_plan, publica=True).count()
        cumplimiento_planificacion = round((plan_publicas/total_plan)*100, 1) if total_plan else 0.0

        clases_total    = _asis.count()
        clases_cerradas = _sf(_asis, estado=getattr(AsistenciaCurso.Estado, "CERR", "CERR")).count() if hasattr(AsistenciaCurso, "Estado") else 0
        uso_recintos    = round((clases_cerradas/clases_total)*100, 1) if clases_total else 0.0

        detalles_total = _det.count()
        presentes      = _sf(_det, estado="P").count()
        ausentes       = _sf(_det, estado="A").count()
        justificadas   = _sf(_det, estado="J").count()
        tasa_asistencia   = round((presentes/detalles_total)*100, 1) if detalles_total else 0.0
        tasa_inasistencia = round(((ausentes+justificadas)/detalles_total)*100, 1) if detalles_total else 0.0
        ratio_est_prof    = round((total_estudiantes/total_profesores), 1) if total_profesores else 0.0

        # Series 12 meses
        hoy = timezone.localdate()
        inicio_12 = (hoy.replace(day=1) - timedelta(days=365)).replace(day=1)
        fin_12    = hoy.replace(day=1)
        meses = []
        y, m = inicio_12.year, inicio_12.month
        while True:
            meses.append(date(y, m, 1))
            if y == fin_12.year and m == fin_12.month:
                break
            m += 1
            if m == 13: m, y = 1, y+1

        est_map = {}
        if est_fecha_field != "id":
            est_mes = (_est.annotate(m=TruncMonth(est_fecha_field))
                           .values("m").annotate(total=Count("id")))
            est_map = { (r["m"].date() if isinstance(r["m"], datetime) else r["m"]) : r["total"] for r in est_mes }

        cla_mes = (_asis.annotate(m=TruncMonth(asis_fecha_field))
                        .values("m").annotate(total=Count("id")))
        cla_map = { (r["m"].date() if isinstance(r["m"], datetime) else r["m"]) : r["total"] for r in cla_mes }

        est_labels = [m_.strftime("%b %Y") for m_ in meses]
        est_series = [est_map.get(m_, 0) for m_ in meses]
        cla_labels = [m_.strftime("%b %Y") for m_ in meses]
        cla_series = [cla_map.get(m_, 0) for m_ in meses]

        # Top inasistencia
        top_rows = (_det.values("asistencia__curso__id","asistencia__curso__nombre")
                        .annotate(total=Count("id"),
                                  ina=Count("id", filter=Q(estado__in=["A","J"]))))

        top_inas = []
        for r in top_rows:
            t = r["total"] or 0
            pct = round((r["ina"]/t)*100, 1) if t else 0.0
            top_inas.append({
                "curso_id": r["asistencia__curso__id"],
                "curso": r["asistencia__curso__nombre"],
                "pct": pct, "total": t
            })
        top_inas = sorted(top_inas, key=lambda x: x["pct"], reverse=True)[:5]

        # Profes con menor % de cierre
        prof_rows = (_asis.values("curso__profesor__first_name","curso__profesor__last_name")
                          .annotate(total=Count("id"),
                                    cerr=Count("id", filter=Q(estado=getattr(AsistenciaCurso.Estado,"CERR","CERR"))))
                          .filter(total__gt=0))
        prof_bad = []
        for r in prof_rows:
            t = r["total"] or 0
            pct = round((r["cerr"]/t)*100, 1) if t else 0.0
            name = f'{r["curso__profesor__first_name"]} {r["curso__profesor__last_name"]}'.strip() or "—"
            prof_bad.append({"prof": name, "pct": pct, "total": t})
        prof_bad = sorted(prof_bad, key=lambda x: x["pct"])[:10]

        return {
            "totales": (total_estudiantes, total_cursos, clases_total, detalles_total),
            "cards": {
                "total_estudiantes": total_estudiantes,
                "activos": activos,
                "total_cursos": total_cursos,
                "cumpl_plan": cumplimiento_planificacion,
                "uso_recintos": uso_recintos,
                "tasa_asist": tasa_asistencia,
                "tasa_inasist": tasa_inasistencia,
                "ratio_ep": ratio_est_prof,
            },
            "series": (est_labels, est_series, cla_labels, cla_series),
            "dist": (presentes, ausentes, justificadas),
            "tops": (top_inas, prof_bad),
        }

    M = _metricas(est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs)
    total_estudiantes, total_cursos, clases_total, detalles_total = M["totales"]


    alerta_filtros = False
    if (total_estudiantes == 0 and clases_total == 0 and detalles_total == 0):
        est_all, curso_all = Estudiante.objects.all(), Curso.objects.all()
        plan_all = Planificacion.objects.all()
        asis_all = AsistenciaCurso.objects.all()
        det_all  = AsistenciaCursoDetalle.objects.all()
        M2 = _metricas(est_all, curso_all, plan_all, asis_all, det_all)
        if any(M2["totales"]):
            M = M2
            alerta_filtros = True

    (est_labels, est_series, cla_labels, cla_series) = M["series"]
    (presentes, ausentes, justificadas) = M["dist"]
    (top_inasistencia, top_prof_bajo_cumpl) = M["tops"]

    cards = M["cards"]
    kpi_cards = [
        {"label":"Total estudiantes","value":cards["total_estudiantes"],"icon":"fa-users","color":"#0ea5e9"},
        {"label":"Activos","value":cards["activos"],"icon":"fa-user-check","color":"#10b981"},
        {"label":"Cursos","value":cards["total_cursos"],"icon":"fa-book","color":"#84cc16"},
        {"label":"Cumpl. planificación","value":f'{cards["cumpl_plan"]}%',"icon":"fa-clipboard-check","color":"#f59e0b"},
        {"label":"Uso recintos (proxy)","value":f'{cards["uso_recintos"]}%',"icon":"fa-building","color":"#a855f7"},
        {"label":"Tasa asistencia","value":f'{cards["tasa_asist"]}%',"icon":"fa-calendar-check","color":"#06b6d4"},
        {"label":"Tasa inasistencia","value":f'{cards["tasa_inasist"]}%',"icon":"fa-calendar-xmark","color":"#ef4444"},
        {"label":"Ratio est./prof.","value":cards["ratio_ep"],"icon":"fa-scale-balanced","color":"#6366f1"},
    ]

    if __dbg:
        print("[KPI][GENERAL] filtros => programa:", programa, "sede:", sede_id, "dep:", dep_id)
        print("[KPI][GENERAL] totales (con/fallback):", M["totales"], "| alerta_filtros:", alerta_filtros)
        print("[KPI][GENERAL] est_series:", len(est_series), "cla_series:", len(cla_series))
        print("[KPI][GENERAL] P/A/J:", presentes, ausentes, justificadas)

    ctx = {
        "modo":"general",
        "programa": programa, "sede_id": str(sede_id), "dep_id": str(dep_id),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "anio_actual": anio_actual,
        "kpi_cards": kpi_cards,


        "est_labels": _j(est_labels), "est_series": _j(est_series),
        "cla_labels": _j(cla_labels), "cla_series": _j(cla_series),

        "dist_presente": presentes, "dist_ausente": ausentes, "dist_justificada": justificadas,
        "top_inasistencia": top_inasistencia,
        "top_prof_bajo_cumpl": top_prof_bajo_cumpl,


        "dia_labels": _j([]), "dia_series": _j([]),

        "semana":"", "rango_str":"", "mes":"", "anio":"",
        "alerta_filtros": alerta_filtros,
    }
    return render(request, "core/dashboard_kpi.html", ctx)

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def dashboard_kpi_semana(request):
    programa   = (request.GET.get("programa") or "").strip()
    sede_id    = request.GET.get("sede") or ""
    dep_id     = request.GET.get("disciplina") or ""
    semana_str = request.GET.get("semana") or ""
    lunes, domingo = _week_range(semana_str)
    anio_actual = timezone.now().year
    __dbg = request.GET.get("__dbg") == "1"

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.select_related("sede", "profesor", "disciplina")
    plan_qs  = Planificacion.objects.select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")\
                                    .filter(semana__range=(lunes, domingo))
    asis_qs  = AsistenciaCurso.objects.select_related("curso", "curso__sede", "curso__disciplina")\
                                      .filter(fecha__range=(lunes, domingo))
    asis_det_qs = AsistenciaCursoDetalle.objects.select_related("asistencia", "asistencia__curso")\
                                               .filter(asistencia__fecha__range=(lunes, domingo))

    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    nuevos_semana = _sf(est_qs, creado__range=(lunes, domingo)).count()

    clases_total    = asis_qs.count()
    clases_cerradas = _sf(asis_qs, estado=getattr(AsistenciaCurso.Estado, "CERR", "CERR")).count() if hasattr(AsistenciaCurso, "Estado") else 0
    uso_recintos    = round((clases_cerradas/clases_total)*100, 1) if clases_total else 0.0

    presentes    = _sf(asis_det_qs, estado=ASIS_P).count()
    ausentes     = _sf(asis_det_qs, estado=ASIS_A).count()
    justificadas = _sf(asis_det_qs, estado=ASIS_J).count()

    dias = [lunes + timedelta(days=i) for i in range(7)]
    dia_labels = [d.strftime("%a %d-%m") for d in dias]
    serie_diaria = (asis_qs.annotate(d=TruncDay("fecha")).values("d").annotate(total=Count("id")))
    mapa = {_to_date(r["d"]): r["total"] for r in serie_diaria}
    dia_series = [mapa.get(d, 0) for d in dias]

    top_rows = (asis_det_qs.values("asistencia__curso__id", "asistencia__curso__nombre")
                .annotate(total=Count("id"),
                          ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    tmp = []
    for r in top_rows:
        total = r["total"] or 0
        pct = round((r["ina"]/total)*100, 1) if total else 0.0
        tmp.append({"curso_id": r["asistencia__curso__id"], "curso": r["asistencia__curso__nombre"], "pct": pct, "total": total})
    top_inasistencia = sorted(tmp, key=lambda x: x["pct"], reverse=True)[:5]

    total_plan = plan_qs.count()
    plan_publicas = _sf(plan_qs, publica=True).count()
    cumplimiento_planificacion = round((plan_publicas/total_plan)*100, 1) if total_plan else 0.0

    ctx = {
        "modo": "semanal",
        "programa": programa, "sede_id": str(sede_id), "dep_id": str(dep_id),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "semana": lunes.isoformat(),
        "rango_str": f"{lunes:%d-%m-%Y} al {domingo:%d-%m-%Y}",
        "anio_actual": anio_actual,
        "kpi_cards": [
            {"label": f"Semana {lunes:%d-%m} a {domingo:%d-%m}", "value": "", "icon": "fa-calendar-week", "color": "#0ea5e9"},
            {"label": "Nuevos (semana)",  "value": nuevos_semana, "icon": "fa-user-plus", "color": "#84cc16"},
            {"label": "Clases registradas","value": clases_total,  "icon": "fa-calendar", "color": "#3b82f6"},
            {"label": "Cumpl. planificación", "value": f"{cumplimiento_planificacion}%", "icon": "fa-clipboard-check", "color": "#f59e0b"},
            {"label": "Uso recintos (proxy)", "value": f"{uso_recintos}%", "icon": "fa-building", "color": "#a855f7"},
        ],

        # ✅ series en JSON
        "dia_labels": _j(dia_labels), "dia_series": _j(dia_series),

        "dist_presente": presentes, "dist_ausente": ausentes, "dist_justificada": justificadas,
        "top_inasistencia": top_inasistencia,

        # vacías para mantener la API del template
        "est_labels": _j([]), "est_series": _j([]),
        "cla_labels": _j([]), "cla_series": _j([]),

        "top_prof_bajo_cumpl": [],
        "mes": "", "anio": "",
    }

    if __dbg:
        print("[KPI][SEMANA] dias:", len(dia_labels), "serie:", len(dia_series),
              "| P/A/J:", presentes, ausentes, justificadas)

    return render(request, "core/dashboard_kpi.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def dashboard_kpi_mes(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""
    mes_str  = request.GET.get("mes") or ""
    inicio, fin, y, m = _month_range(mes_str)
    anio_actual = y
    __dbg = request.GET.get("__dbg") == "1"

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.select_related("sede", "profesor", "disciplina")
    plan_qs  = Planificacion.objects.select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")\
                                    .filter(semana__range=(inicio, fin))
    asis_qs  = AsistenciaCurso.objects.select_related("curso", "curso__sede", "curso__disciplina")\
                                      .filter(fecha__range=(inicio, fin))
    asis_det_qs = AsistenciaCursoDetalle.objects.select_related("asistencia", "asistencia__curso")\
                                               .filter(asistencia__fecha__range=(inicio, fin))

    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    nuevos_mes = _sf(est_qs, creado__range=(inicio, fin)).count()

    clases_total    = asis_qs.count()
    clases_cerradas = _sf(asis_qs, estado=getattr(AsistenciaCurso.Estado, "CERR", "CERR")).count() if hasattr(AsistenciaCurso, "Estado") else 0
    uso_recintos    = round((clases_cerradas/clases_total)*100, 1) if clases_total else 0.0

    presentes    = _sf(asis_det_qs, estado=ASIS_P).count()
    ausentes     = _sf(asis_det_qs, estado=ASIS_A).count()
    justificadas = _sf(asis_det_qs, estado=ASIS_J).count()

    dias = [(inicio + timedelta(days=i)) for i in range((fin - inicio).days + 1)]
    dia_labels = [d.strftime("%d-%b") for d in dias]
    serie_diaria = (asis_qs.annotate(d=TruncDay("fecha")).values("d").annotate(total=Count("id")))
    mapa = {_to_date(r["d"]): r["total"] for r in serie_diaria}
    dia_series = [mapa.get(d, 0) for d in dias]

    top_rows = (asis_det_qs.values("asistencia__curso__id", "asistencia__curso__nombre")
                .annotate(total=Count("id"),
                          ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    tmp = []
    for r in top_rows:
        total = r["total"] or 0
        pct = round((r["ina"]/total)*100, 1) if total else 0.0
        tmp.append({"curso_id": r["asistencia__curso__id"], "curso": r["asistencia__curso__nombre"], "pct": pct, "total": total})
    top_inasistencia = sorted(tmp, key=lambda x: x["pct"], reverse=True)[:5]

    total_plan = plan_qs.count()
    plan_publicas = _sf(plan_qs, publica=True).count()
    cumplimiento_planificacion = round((plan_publicas/total_plan)*100, 1) if total_plan else 0.0

    ctx = {
        "modo": "mensual",
        "programa": programa, "sede_id": str(sede_id), "dep_id": str(dep_id),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "anio_actual": anio_actual,
        "kpi_cards": [
            {"label": f"Mes {inicio:%B %Y}", "value": "", "icon": "fa-calendar-days", "color": "#0ea5e9"},
            {"label": "Nuevos (mes)", "value": nuevos_mes, "icon": "fa-user-plus", "color": "#84cc16"},
            {"label": "Clases registradas", "value": clases_total, "icon": "fa-calendar", "color": "#3b82f6"},
            {"label": "Cumpl. planificación", "value": f"{cumplimiento_planificacion}%", "icon": "fa-clipboard-check", "color": "#f59e0b"},
            {"label": "Uso recintos (proxy)", "value": f"{uso_recintos}%", "icon": "fa-building", "color": "#a855f7"},
        ],

        # ✅ series en JSON
        "dia_labels": _j(dia_labels), "dia_series": _j(dia_series),

        "dist_presente": presentes, "dist_ausente": ausentes, "dist_justificada": justificadas,
        "top_inasistencia": top_inasistencia,

        # vacías para mantener la API del template
        "est_labels": _j([]), "est_series": _j([]),
        "cla_labels": _j([]), "cla_series": _j([]),

        "top_prof_bajo_cumpl": [],
        "semana": "", "rango_str": "", "mes": f"{inicio:%Y-%m}", "anio": "",
    }

    if __dbg:
        print("[KPI][MES] dias:", len(dia_labels), "serie:", len(dia_series),
              "| P/A/J:", presentes, ausentes, justificadas)

    return render(request, "core/dashboard_kpi.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def dashboard_kpi_anio(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""
    anio_str = request.GET.get("anio") or ""
    inicio, fin, y = _year_range(anio_str)
    anio_actual = y
    __dbg = request.GET.get("__dbg") == "1"

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.select_related("sede", "profesor", "disciplina")
    plan_qs  = Planificacion.objects.select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")\
                                    .filter(semana__range=(inicio, fin))
    asis_qs  = AsistenciaCurso.objects.select_related("curso", "curso__sede", "curso__disciplina")\
                                      .filter(fecha__range=(inicio, fin))
    asis_det_qs = AsistenciaCursoDetalle.objects.select_related("asistencia", "asistencia__curso")\
                                               .filter(asistencia__fecha__range=(inicio, fin))

    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    clases_total    = asis_qs.count()
    clases_cerradas = _sf(asis_qs, estado=getattr(AsistenciaCurso.Estado, "CERR", "CERR")).count() if hasattr(AsistenciaCurso, "Estado") else 0
    uso_recintos    = round((clases_cerradas/clases_total)*100, 1) if clases_total else 0.0

    presentes    = _sf(asis_det_qs, estado=ASIS_P).count()
    ausentes     = _sf(asis_det_qs, estado=ASIS_A).count()
    justificadas = _sf(asis_det_qs, estado=ASIS_J).count()

    meses = _serie_meses_completos(inicio, fin)
    cla_mes = (asis_qs.annotate(m=TruncMonth("fecha"))
               .values("m").annotate(total=Count("id")))
    cla_map = {_to_date(r["m"]): r["total"] for r in cla_mes}
    cla_labels = [m.strftime("%b %Y") for m in meses]
    cla_series = [cla_map.get(m, 0) for m in meses]

    top_rows = (asis_det_qs.values("asistencia__curso__id", "asistencia__curso__nombre")
                .annotate(total=Count("id"),
                          ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    tmp = []
    for r in top_rows:
        total = r["total"] or 0
        pct = round((r["ina"]/total)*100, 1) if total else 0.0
        tmp.append({"curso_id": r["asistencia__curso__id"], "curso": r["asistencia__curso__nombre"], "pct": pct, "total": total})
    top_inasistencia = sorted(tmp, key=lambda x: x["pct"], reverse=True)[:5]

    total_plan = plan_qs.count()
    plan_publicas = _sf(plan_qs, publica=True).count()
    cumplimiento_planificacion = round((plan_publicas/total_plan)*100, 1) if total_plan else 0.0

    ctx = {
        "modo": "anual",
        "programa": programa, "sede_id": str(sede_id), "dep_id": str(dep_id),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "anio_actual": anio_actual,
        "kpi_cards": [
            {"label": f"Año {y}", "value": "", "icon": "fa-calendar", "color": "#0ea5e9"},
            {"label": "Clases registradas", "value": clases_total, "icon": "fa-calendar", "color": "#3b82f6"},
            {"label": "Cumpl. planificación", "value": f"{cumplimiento_planificacion}%", "icon": "fa-clipboard-check", "color": "#f59e0b"},
            {"label": "Uso recintos (proxy)", "value": f"{uso_recintos}%", "icon": "fa-building", "color": "#a855f7"},
        ],


        "cla_labels": _j(cla_labels), "cla_series": _j(cla_series),

        "dist_presente": presentes, "dist_ausente": ausentes, "dist_justificada": justificadas,
        "top_inasistencia": top_inasistencia,


        "est_labels": _j([]), "est_series": _j([]),
        "dia_labels": _j([]), "dia_series": _j([]),

        "top_prof_bajo_cumpl": [],
        "semana": "", "rango_str": "", "mes": "", "anio": f"{y}",
    }

    if __dbg:
        print("[KPI][AÑO] meses:", len(cla_labels), "serie:", len(cla_series),
              "| P/A/J:", presentes, ausentes, justificadas)

    return render(request, "core/dashboard_kpi.html", ctx)


# ----------------- EXPORTS -----------------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_general_pdf(request):
    resp = dashboard_kpi(request)
    pdf = HTML(string=resp.content.decode("utf-8"), base_url=request.build_absolute_uri()).write_pdf()
    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = 'attachment; filename="kpi_general.pdf"'
    return r

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_general_excel(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.all()
    plan_qs  = Planificacion.objects.all()
    asis_qs  = AsistenciaCurso.objects.all()
    asis_det_qs = AsistenciaCursoDetalle.objects.all()
    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    resumen = [{
        "Total estudiantes": est_qs.count(),
        "Activos": _sf(est_qs, activo=True).count(),
        "Cursos": curso_qs.count(),
        "Planificaciones": plan_qs.count(),
        "Clases registradas": asis_qs.count(),
        "Detalles asistencia": asis_det_qs.count(),
    }]
    df_resumen = pd.DataFrame(resumen)

    est_fecha_field = _first_existing_field(Estudiante, [
        "creado", "fecha_creacion", "created_at", "created", "fecha_registro", "fecha"
    ]) or None

    if est_fecha_field:
        est_mes = (est_qs.annotate(mes=TruncMonth(est_fecha_field))
                        .values("mes").annotate(total=Count("id")).order_by("mes"))
        df_est_mes = pd.DataFrame([{"Mes": e["mes"].strftime("%Y-%m"), "Nuevos": e["total"]} for e in est_mes])
    else:
        df_est_mes = pd.DataFrame(columns=["Mes", "Nuevos"])

    cla_mes = (asis_qs.annotate(mes=TruncMonth("fecha"))
                      .values("mes").annotate(total=Count("id")).order_by("mes"))
    df_cla_mes = pd.DataFrame([{"Mes": c["mes"].strftime("%Y-%m"), "Clases": c["total"]} for c in cla_mes])

    top = (asis_det_qs.values("asistencia__curso__nombre")
           .annotate(total=Count("id"), ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    rows = [{
        "Curso": r["asistencia__curso__nombre"],
        "Registros": r["total"],
        "% Inasistencia": round((r["ina"]/r["total"])*100, 1) if r["total"] else 0
    } for r in top]
    df_top = pd.DataFrame(sorted(rows, key=lambda x: x["% Inasistencia"], reverse=True)[:20])

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="kpi_general.xlsx"'
    with pd.ExcelWriter(resp, engine="openpyxl") as writer:
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)
        df_est_mes.to_excel(writer, sheet_name="Estudiantes por mes", index=False)
        df_cla_mes.to_excel(writer, sheet_name="Clases por mes", index=False)
        df_top.to_excel(writer, sheet_name="Top inasistencia", index=False)
    return resp

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_semana_pdf(request):
    resp = dashboard_kpi_semana(request)
    pdf = HTML(string=resp.content.decode("utf-8"), base_url=request.build_absolute_uri()).write_pdf()
    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = 'attachment; filename="kpi_semana.pdf"'
    return r

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_semana_excel(request):
    programa   = (request.GET.get("programa") or "").strip()
    sede_id    = request.GET.get("sede") or ""
    dep_id     = request.GET.get("disciplina") or ""
    semana_str = request.GET.get("semana") or ""
    lunes, domingo = _week_range(semana_str)

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.all()
    plan_qs  = Planificacion.objects.filter(semana__range=(lunes, domingo))
    asis_qs  = AsistenciaCurso.objects.filter(fecha__range=(lunes, domingo))
    asis_det_qs = AsistenciaCursoDetalle.objects.filter(asistencia__fecha__range=(lunes, domingo))
    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    resumen = [{
        "Semana": f"{lunes:%Y-%m-%d} a {domingo:%Y-%m-%d}",
        "Nuevos (semana)": _sf(est_qs, creado__range=(lunes, domingo)).count(),
        "Clases registradas": asis_qs.count(),
        "Planificaciones": plan_qs.count(),
        "Detalles asistencia": asis_det_qs.count(),
    }]
    df_resumen = pd.DataFrame(resumen)

    serie_diaria = (asis_qs.annotate(dia=TruncDay("fecha"))
                    .values("dia").annotate(total=Count("id")).order_by("dia"))
    df_dias = pd.DataFrame([{"Día": r["dia"].strftime("%Y-%m-%d"), "Clases": r["total"]} for r in serie_diaria])

    top = (asis_det_qs.values("asistencia__curso__nombre")
           .annotate(total=Count("id"), ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    rows = [{
        "Curso": r["asistencia__curso__nombre"], "Registros": r["total"],
        "% Inasistencia": round((r["ina"]/r["total"])*100, 1) if r["total"] else 0
    } for r in top]
    df_top = pd.DataFrame(sorted(rows, key=lambda x: x["% Inasistencia"], reverse=True)[:20])

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="kpi_semana.xlsx"'
    with pd.ExcelWriter(resp, engine="openpyxl") as writer:
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)
        df_dias.to_excel(writer, sheet_name="Clases por día", index=False)
        df_top.to_excel(writer, sheet_name="Top inasistencia", index=False)
    return resp

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_mes_pdf(request):
    resp = dashboard_kpi_mes(request)
    pdf = HTML(string=resp.content.decode("utf-8"), base_url=request.build_absolute_uri()).write_pdf()
    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = 'attachment; filename="kpi_mes.pdf"'
    return r

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_mes_excel(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""
    mes_str  = request.GET.get("mes") or ""
    inicio, fin, y, m = _month_range(mes_str)

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.all()
    plan_qs  = Planificacion.objects.filter(semana__range=(inicio, fin))
    asis_qs  = AsistenciaCurso.objects.filter(fecha__range=(inicio, fin))
    asis_det_qs = AsistenciaCursoDetalle.objects.filter(asistencia__fecha__range=(inicio, fin))
    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    resumen = [{
        "Mes": f"{inicio:%Y-%m}",
        "Nuevos (mes)": _sf(est_qs, creado__range=(inicio, fin)).count(),
        "Clases registradas": asis_qs.count(),
        "Planificaciones": plan_qs.count(),
        "Detalles asistencia": asis_det_qs.count(),
    }]
    df_resumen = pd.DataFrame(resumen)

    serie_diaria = (asis_qs.annotate(dia=TruncDay("fecha"))
                    .values("dia").annotate(total=Count("id")).order_by("dia"))
    df_dias = pd.DataFrame([{"Día": r["dia"].strftime("%Y-%m-%d"), "Clases": r["total"]} for r in serie_diaria])

    top = (asis_det_qs.values("asistencia__curso__nombre")
           .annotate(total=Count("id"), ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    rows = [{
        "Curso": r["asistencia__curso__nombre"], "Registros": r["total"],
        "% Inasistencia": round((r["ina"]/r["total"])*100, 1) if r["total"] else 0
    } for r in top]
    df_top = pd.DataFrame(sorted(rows, key=lambda x: x["% Inasistencia"], reverse=True)[:20])

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="kpi_mes.xlsx"'
    with pd.ExcelWriter(resp, engine="openpyxl") as writer:
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)
        df_dias.to_excel(writer, sheet_name="Clases por día", index=False)
        df_top.to_excel(writer, sheet_name="Top inasistencia", index=False)
    return resp

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_anio_pdf(request):
    # Llamamos al dashboard normal
    resp = dashboard_kpi_anio(request)


    html = resp.content.decode("utf-8")


    html = html.replace("var(--primary-600)", "#008080")
    html = html.replace("var(--primary-700)", "#006666")
    html = html.replace("currentColor", "#000000")


    html = re.sub(r"<svg.*?</svg>", "", html, flags=re.DOTALL)


    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()


    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = 'attachment; filename="kpi_anio.pdf"'
    return r

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def exportar_kpi_anio_excel(request):
    programa = (request.GET.get("programa") or "").strip()
    sede_id  = request.GET.get("sede") or ""
    dep_id   = request.GET.get("disciplina") or ""
    anio_str = request.GET.get("anio") or ""
    inicio, fin, y = _year_range(anio_str)

    est_qs   = Estudiante.objects.all()
    curso_qs = Curso.objects.all()
    plan_qs  = Planificacion.objects.filter(semana__range=(inicio, fin))
    asis_qs  = AsistenciaCurso.objects.filter(fecha__range=(inicio, fin))
    asis_det_qs = AsistenciaCursoDetalle.objects.filter(asistencia__fecha__range=(inicio, fin))
    est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs = _aplicar_filtros_basicos(
        est_qs, curso_qs, plan_qs, asis_qs, asis_det_qs, programa, sede_id, dep_id
    )

    resumen = [{
        "Año": f"{y}",
        "Clases registradas": asis_qs.count(),
        "Planificaciones": plan_qs.count(),
        "Detalles asistencia": asis_det_qs.count(),
    }]
    df_resumen = pd.DataFrame(resumen)

    cla_mes = (asis_qs.annotate(mes=TruncMonth("fecha"))
               .values("mes").annotate(total=Count("id")).order_by("mes"))
    df_cla_mes = pd.DataFrame([{"Mes": c["mes"].strftime("%Y-%m"), "Clases": c["total"]} for c in cla_mes])

    top = (asis_det_qs.values("asistencia__curso__nombre")
           .annotate(total=Count("id"), ina=Count("id", filter=Q(estado__in=[ASIS_A, ASIS_J]))))
    rows = [{
        "Curso": r["asistencia__curso__nombre"], "Registros": r["total"],
        "% Inasistencia": round((r["ina"]/r["total"])*100, 1) if r["total"] else 0
    } for r in top]
    df_top = pd.DataFrame(sorted(rows, key=lambda x: x["% Inasistencia"], reverse=True)[:20])

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="kpi_anio.xlsx"'
    with pd.ExcelWriter(resp, engine="openpyxl") as writer:
        pd.DataFrame(resumen).to_excel(writer, sheet_name="Resumen", index=False)
        df_cla_mes.to_excel(writer, sheet_name="Clases por mes", index=False)
        df_top.to_excel(writer, sheet_name="Top inasistencia", index=False)
    return resp

@require_http_methods(["GET"])
def comunicados_public(request):
    items = Comunicado.objects.publics().order_by("-creado")
    return render(request, "core/comunicado_public.html", {"items": items})

@require_http_methods(["GET"])
def comunicado_public_detail(request, pk:int):
    obj = get_object_or_404(Comunicado.objects.publics(), pk=pk)
    return render(request, "core/comunicado_public", {"obj": obj})