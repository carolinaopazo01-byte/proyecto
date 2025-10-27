# applications/usuarios/views_profesor.py
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.db import transaction
from django.db.models import Q, Count
from django.contrib import messages
from django.urls import reverse

from applications.core.models import Curso, Planificacion, Comunicado
from applications.atleta.models import AsistenciaAtleta, Clase, Inscripcion
from .forms_profesor import PlanificacionForm, ComunicadoForm


# ---------------- helpers ----------------
def _es_prof(user) -> bool:
    return (getattr(user, "tipo_usuario", "") or "").upper() == "PROF"


# ---------------- panel ----------------
@login_required
def panel_profesor(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    hoy = timezone.localdate()
    fin_semana = hoy + timedelta(days=7)

    cursos_total = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .select_related("disciplina", "sede")
        .distinct()
    )

    clases = (
        Clase.objects.filter(profesor=request.user, fecha__range=(hoy, fin_semana))
        .select_related("curso")
        .order_by("fecha", "hora_inicio")
    )

    pendientes_planif = Planificacion.objects.filter(
        curso__in=cursos_total, archivo__isnull=True, comentarios__isnull=True
    ).count()

    sin_asistencia = (
        Clase.objects
        .filter(profesor=request.user, fecha__lt=hoy, asistencias__isnull=True)
        .distinct()
        .count()
    )

    ctx = {
        "cursos": cursos_total,
        "clases": clases,
        "alertas": {"planificaciones": pendientes_planif, "inasistencias": sin_asistencia},
    }
    return render(request, "profesor/panel_profesor.html", ctx)


# ---------------- mis cursos ----------------
@login_required
def mis_cursos(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    cursos = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .distinct()
        .select_related("disciplina", "sede")
        .prefetch_related("horarios")
        # cuenta inscripciones ACTIVAS por curso
        .annotate(alumnos_count=Count("inscripciones", filter=Q(inscripciones__estado="ACTIVA"), distinct=True))
    )
    return render(request, "profesor/mis_cursos.html", {"cursos": cursos})


# ---------------- asistencia: listado simple ----------------
@login_required
def asistencia_listado(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    cursos = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .distinct()
    )
    return render(request, "profesor/asistencia_listado.html", {"cursos": cursos})


# ---------------- asistencia: tomar ----------------
@login_required
@transaction.atomic
def asistencia_tomar(request, curso_id):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    curso = get_object_or_404(
        Curso.objects.filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user)).distinct(),
        pk=curso_id,
    )

    hoy = timezone.localdate()

    clase, _ = Clase.objects.get_or_create(
        curso=curso,
        profesor=request.user,
        fecha=hoy,
        defaults={
            "hora_inicio": timezone.now().time(),
            "hora_fin": (timezone.now() + timedelta(minutes=90)).time(),
            "tema": f"Sesión {hoy.strftime('%d/%m')}",
            "estado": "PEND",
        }
    )

    inscritos = (
        Inscripcion.objects
        .filter(curso=curso, estado="ACTIVA")
        .select_related("atleta", "atleta__usuario")
        .order_by("atleta__usuario__last_name", "atleta__usuario__first_name", "atleta__rut")
    )

    # Asistencias ya guardadas para esta clase
    asist_qs = AsistenciaAtleta.objects.filter(
        clase=clase,
        atleta_id__in=inscritos.values_list("atleta_id", flat=True),
    )
    asist_by_atleta = {a.atleta_id: a for a in asist_qs}

    # Filas para la plantilla (estado previo + observación)
    rows = []
    for ins in inscritos:
        a = asist_by_atleta.get(ins.atleta_id)
        if a:
            if a.presente:
                code = "P"
            elif a.justificado:
                code = "J"
            else:
                code = "A"
            obs = a.observaciones or ""
        else:
            code = ""
            obs = ""
        rows.append({"ins": ins, "code": code, "obs": obs})

    if request.method == "POST":
        accion = request.POST.get("accion")  # 'entrada' | 'salida' | 'guardar'

        if accion == "entrada" and clase.estado == "PEND":
            clase.estado = "ENCU"
            clase.inicio_real = timezone.now()
            clase.save(update_fields=["estado", "inicio_real"])

        elif accion == "salida" and clase.estado in ("PEND", "ENCU"):
            clase.estado = "CERR"
            clase.fin_real = timezone.now()
            clase.save(update_fields=["estado", "fin_real"])

        elif accion == "guardar":
            guardados = 0
            for ins in inscritos:
                estado = request.POST.get(f"estado_{ins.pk}")  # 'P' | 'A' | 'J'
                obs = request.POST.get(f"obs_{ins.pk}") or ""
                presente = (estado == "P")
                justificado = (estado == "J")

                AsistenciaAtleta.objects.update_or_create(
                    clase=clase,
                    atleta=ins.atleta,
                    defaults={
                        "presente": presente,
                        "justificado": justificado,
                        "observaciones": obs,
                        "registrada_por": request.user,
                    }
                )
                guardados += 1

            messages.success(request, f"Asistencia guardada para {guardados} alumno(s).")

        return redirect("usuarios:asistencia_tomar", curso_id=curso.id)

    p_count = sum(1 for r in rows if r["code"] == "P")
    j_count = sum(1 for r in rows if r["code"] == "J")
    a_count = sum(1 for r in rows if r["code"] == "A")
    resumen = {"P": p_count, "A": a_count, "J": j_count, "total": len(rows)}

    return render(
        request,
        "profesor/asistencia_tomar.html",
        {"curso": curso, "rows": rows, "clase": clase, "resumen": resumen}
    )


# ---------------- planificaciones ----------------
@login_required
def planificaciones(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    cursos_qs = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .distinct()
    )

    curso_f = request.GET.get("curso") or ""
    qs = (
        Planificacion.objects
        .filter(curso__in=cursos_qs)
        .select_related("curso")
        .order_by("-semana", "-id")
    )
    if curso_f:
        qs = qs.filter(curso_id=curso_f)

    if request.method == "POST":
        form = PlanificacionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            plan = form.save(commit=False)
            if not cursos_qs.filter(pk=plan.curso_id).exists():
                return HttpResponseForbidden("Curso inválido.")
            plan.autor = request.user
            plan.save()
            messages.success(request, "Planificación subida correctamente.")
            redir = "usuarios:planificaciones_prof"
            if curso_f:
                return redirect(f"{reverse(redir)}?curso={curso_f}")
            return redirect(redir)
    else:
        initial = {}
        if curso_f:
            initial["curso"] = curso_f
        form = PlanificacionForm(user=request.user, initial=initial)

    return render(request, "profesor/planificaciones.html", {
        "planificaciones": qs,
        "form": form,
        "cursos_qs": cursos_qs,
        "curso_f": curso_f,
    })


# ---------------- comunicados ----------------
@login_required
def comunicados(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    cursos_qs = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .distinct()
    )

    comunicados = (Comunicado.objects
                   .filter(autor=request.user)
                   .select_related(*[n for n in ["curso", "destinatario_curso"] if hasattr(Comunicado, n)])
                   .order_by("-creado") if hasattr(Comunicado, "creado") else
                   Comunicado.objects.filter(autor=request.user).order_by("-id"))

    def _set_first_attr(obj, value, *names):
        for n in names:
            if hasattr(obj, n):
                setattr(obj, n, value)
                return True
        return False

    if request.method == "POST":
        form = ComunicadoForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            if cd.get("curso") and not cursos_qs.filter(pk=cd["curso"].pk).exists():
                return HttpResponseForbidden("Curso inválido.")

            obj = Comunicado()
            if hasattr(Comunicado, "autor"):
                obj.autor = request.user

            _set_first_attr(obj, cd.get("curso"),
                            "curso", "destinatario_curso", "para_curso")

            _set_first_attr(obj, cd.get("titulo"),
                            "titulo", "asunto")

            _set_first_attr(obj, cd.get("cuerpo"),
                            "cuerpo", "contenido", "mensaje", "texto", "descripcion")

            _set_first_attr(obj, cd.get("publico", False),
                            "publico", "publica", "es_publico")

            obj.save()
            messages.success(request, "Comunicado publicado.")
            return redirect("usuarios:comunicados_prof")
    else:
        form = ComunicadoForm(user=request.user)

    return render(
        request,
        "profesor/comunicados.html",
        {"form": form, "comunicados": comunicados}
    )


# ---------------- perfil ----------------
@login_required
def mi_perfil(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    return render(request, "profesor/perfil.html", {"profesor": request.user})
