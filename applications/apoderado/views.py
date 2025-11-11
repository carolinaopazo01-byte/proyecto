from datetime import timedelta, date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.apps import apps

from .utils import get_model
from .utils import (
    hijos_de_apoderado, porcentaje_asistencia_semana, proxima_clase_de,
    proximas_citas_para, curso_actual_de
)

from applications.core.models import Comunicado, Estudiante
from applications.atleta.models import Clase, AsistenciaAtleta
###########################

@login_required
def dashboard(request):
    hoy = timezone.localdate()
    inicio = hoy - timedelta(days=hoy.weekday())  # lunes
    fin = inicio + timedelta(days=6)             # domingo

    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)



    hijo_ref = hijos[0] if hijos else None
    asistencia_pct = porcentaje_asistencia_semana(hijo_ref) if hijo_ref else None
    proxima = proxima_clase_de(hijo_ref) if hijo_ref else None
    citas = proximas_citas_para(hijo_ref) if hijo_ref else 0


    atletas = []
    for h in hijos:
        curso = curso_actual_de(h)
        etiqueta = None
        if curso:
            sede = getattr(curso.sede, "nombre", "")
            etiqueta = f"{curso.disciplina} {('- ' + curso.categoria) if curso.categoria else ''}"
            etiqueta = etiqueta.strip()
            if sede:
                etiqueta = f"{etiqueta}, {sede}" if etiqueta else sede
        atletas.append({
            "id": h.id,
            "nombre": f"{h.nombres} {h.apellidos}".strip(),
            "descripcion": etiqueta or "—",
        })

    ctx = {
        "apoderado": apoderado,
        #"hijos": hijos,
        "atletas": hijos,
        "asistencia_pct": asistencia_pct,
        "proxima_clase": proxima,
        "citas": citas,
        "inicio": inicio,
        "fin": fin,
        "registros": [],  # si quieres mantener la tabla pequeña de semana
    }
    return render(request, "apoderado/dashboard.html", ctx)

@login_required
def asistencia(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)

    sel = request.GET.get("hijo")
    if sel and hasattr(hijos, "filter"):
        hijo = hijos.filter(pk=sel).first()
    else:
        hijo = hijos.first() if hasattr(hijos, "first") else None

    items = []
    Asis = (
        get_model("core.AsistenciaAtleta")
        or get_model("core.AsistenciaAlumno")
        or get_model("atleta.Asistencia")
    )
    if Asis and hijo:
        hoy = timezone.localdate()
        ini = hoy.replace(day=1)
        fin = (ini + timedelta(days=40)).replace(day=1) - timedelta(days=1)

        fk_name = None
        for f in Asis._meta.fields:
            if f.is_relation and getattr(f, "related_model", None) == hijo.__class__:
                fk_name = f.name
                break

        if fk_name:
            items = (
                Asis.objects.select_related("asistencia", "asistencia__profesor")
                .filter(**{fk_name: hijo, "asistencia__fecha__range": (ini, fin)})
                .order_by("-asistencia__fecha")
            )

    return render(
        request,
        "apoderado/asistencia.html",
        {"hijos": hijos, "hijo": hijo, "items": items},
    )


@login_required
def planificacion(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)
    hijo = hijos.first() if hasattr(hijos, "first") else None

    Plan = apps.get_model("core", "Planificacion", require_ready=False)
    Curso = apps.get_model("core", "Curso", require_ready=False)
    items = []
    if Plan and hijo:
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        qs = Plan.objects.filter(semana=lunes)
        if Curso and "curso" in [f.name for f in Plan._meta.fields]:
            prox = proxima_clase_de(hijo)
            curso = prox["curso"] if prox else None
            if curso:
                qs = qs.filter(curso=curso)
        items = list(qs.order_by("curso__nombre" if Curso else "id"))

    return render(
        request, "apoderado/planificacion.html", {"hijos": hijos, "hijo": hijo, "items": items}
    )

@login_required
def evaluaciones(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)
    hijo = hijos.first() if hasattr(hijos, "first") else None

    Ficha = apps.get_model("pmul", "FichaClinica", require_ready=False)
    items = []
    if Ficha and hijo:
        items = list(
            Ficha.objects.filter(paciente=hijo, publicar_profesor=True).order_by("-fecha")[:200]
        )
    return render(request, "apoderado/evaluaciones.html", {"hijos": hijos, "hijo": hijo, "items": items})


@login_required
def comunicados(request):
    Com = apps.get_model("core", "Comunicado", require_ready=False)
    items = list(Com.objects.order_by("-creado")[:200]) if Com else []
    return render(request, "apoderado/comunicados.html", {"items": items})


@login_required
def protocolos(request):
    Doc = (apps.get_model("core", "Documento") or apps.get_model("core", "Protocolo"))
    items = list(Doc.objects.order_by("-id")[:200]) if Doc else []
    return render(request, "apoderado/protocolos.html", {"items": items})

@login_required
def alumno_detalle(request, pk):
    Estudiante = apps.get_model("core", "Estudiante")
    alumno = get_object_or_404(Estudiante, pk=pk)

    apoderado = request.user


    campos = [f.name for f in Estudiante._meta.fields]
    autorizado = False


    if "apoderado" in campos:
        autorizado = getattr(alumno, "apoderado_id", None) == apoderado.id


    if not autorizado and "apoderado_rut" in campos:
        def _norm_rut(r):
            if not r:
                return ""
            r = str(r).replace(".", "").replace(" ", "").replace("–", "-").replace("—", "-").upper()
            if "-" not in r and len(r) >= 2:
                r = r[:-1] + "-" + r[-1]
            return r
        rut_user = _norm_rut(getattr(apoderado, "rut", "") or getattr(apoderado, "username", ""))
        rut_alum = _norm_rut(getattr(alumno, "apoderado_rut", ""))
        autorizado = (rut_user and rut_alum and rut_user == rut_alum)

    if not autorizado:
        messages.error(request, "No tienes permisos para ver este deportista.")
        return redirect("apoderado:dashboard")


    Curso = apps.get_model("core", "Curso")
    CursoHorario = apps.get_model("core", "CursoHorario")
    prox = None
    if Curso and CursoHorario and "curso" in campos:
        curso = getattr(alumno, "curso", None)
        if curso:
            ahora = timezone.localtime()
            horarios = CursoHorario.objects.filter(curso=curso).order_by("dia", "hora_inicio")
            for add_d in range(0, 14):
                d = ahora.date() + timedelta(days=add_d)
                for h in horarios.filter(dia=d.weekday()):
                    dt = timezone.make_aware(timezone.datetime.combine(d, h.hora_inicio))
                    if dt >= ahora:
                        prox = {"fecha": d, "hora": h.hora_inicio, "curso": curso}
                        break
                if prox:
                    break


    Plan = apps.get_model("core", "Planificacion")
    planifs = []
    if Plan:
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        qs = Plan.objects.filter(semana=lunes)
        if "curso" in [f.name for f in Plan._meta.fields] and getattr(alumno, "curso_id", None):
            qs = qs.filter(curso=alumno.curso)
        planifs = list(qs.order_by("-creado")[:10])

    return render(
        request,
        "apoderado/alumno_detalle.html",
        {
            "alumno": alumno,
            "proxima_clase": prox,
            "planificaciones": planifs,
        },
    )

@login_required
def dashboard_apoderado(request):
    user = request.user
    atletas = Estudiante.objects.filter(apoderado__usuario=user).select_related("curso", "curso__profesor")

    # % asistencia promedio
    asistencia_pct = None
    if atletas.exists():
        total_registros = AsistenciaAtleta.objects.filter(atleta__in=atletas).count()
        presentes = AsistenciaAtleta.objects.filter(atleta__in=atletas, presente=True).count()
        asistencia_pct = round((presentes / total_registros) * 100, 1) if total_registros else None

    # próxima clase
    prox_clase = (
        Clase.objects.filter(
            sede_deporte__deporte__in=[a.curso.disciplina for a in atletas],
            fecha__gte=timezone.localdate()
        )
        .select_related("sede_deporte__sede", "profesor")
        .order_by("fecha", "hora_inicio")
        .first()
    )

    # próximas citas del equipo multidisciplinario
    prox_citas = 0

    # comunicados dirigidos a apoderados o todos
    comunicados = (
        Comunicado.objects.filter(dirigido_a__in=["APODERADOS", "TODOS"])
        .order_by("-creado")[:5]
    )

    return render(request, "apoderado/dashboard.html", {
        "atletas": atletas,
        "asistencia_pct": asistencia_pct,
        "prox_clase": prox_clase,
        "prox_citas": prox_citas,
        "comunicados": comunicados,
    })