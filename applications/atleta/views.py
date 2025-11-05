# applications/atleta/views.py
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password, ValidationError as PwdValidationError
from django.db.models import Q, Count
from django.utils import timezone

from applications.usuarios.utils import role_required, normalizar_rut, formatear_rut
from applications.usuarios.models import Usuario
from applications.core.models import Estudiante, Curso, Planificacion
from applications.usuarios.decorators import role_required

from .models import AsistenciaAtleta, Clase, Inscripcion

from datetime import date, datetime, timedelta

# ----------------- helpers de semana -----------------
def _mon(d: date) -> date:
    return d - timedelta(days=d.weekday())
def _sun(d: date) -> date:
    return _mon(d) + timedelta(days=6)

# ================== MI CURSO ==================
@role_required("ATLE")   # o @login_required si no tienes el decorador
def mis_cursos(request):
    # 1) Primero intentamos con Inscripcion (camino “oficial”)
    ins = (Inscripcion.objects
           .select_related("curso", "curso__sede", "curso__disciplina", "curso__profesor")
           .filter(atleta__usuario=request.user))

    items = list(ins)

    # 2) Si no hay Inscripcion, hacemos FALLBACK: buscamos Estudiante por RUT
    if not items:
        rut_norm = normalizar_rut(getattr(request.user, "rut", "") or request.user.username)
        est = Estudiante.objects.filter(rut__in=[rut_norm, formatear_rut(rut_norm)]).select_related("curso").first()
        if est and getattr(est, "curso", None):
            # objeto liviano con los mismos atributos que usa el template
            class _InscripcionLite:
                curso = est.curso
            items = [_InscripcionLite()]

    return render(request, "atleta/mis_cursos.html", {"inscripciones": items})

# ================== ASISTENCIA (vista semanal + KPIs) ==================
@role_required(Usuario.Tipo.ATLE)
def asistencia_semana(request):
    from datetime import datetime, timedelta
    raw = (request.GET.get("semana") or "").strip()
    try:
        dia = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        dia = timezone.localdate()
    d1, d2 = dia - timedelta(days=dia.weekday()), dia + timedelta(days=(6 - dia.weekday()))

    qs = AsistenciaAtleta.objects.select_related("clase").filter(
        atleta__usuario=request.user,
        clase__fecha__range=(d1, d2),
    ).order_by("clase__fecha", "clase__hora_inicio")

    # KPIs
    total_hist_inasist = AsistenciaAtleta.objects.filter(
        atleta__usuario=request.user, presente=False
    ).count()
    semana_inasist = qs.filter(presente=False).count()

    hoy = timezone.localdate()
    m1 = hoy.replace(day=1)
    m2 = (m1 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    mes_qs = AsistenciaAtleta.objects.filter(atleta__usuario=request.user, clase__fecha__range=(m1, m2))
    presentes_mes = mes_qs.filter(presente=True).count()
    total_mes = mes_qs.count()
    pct_mes = round((presentes_mes / total_mes) * 100, 1) if total_mes else 0

    ctx = {
        "items": qs,
        "desde": d1, "hasta": d2,
        "semana": d1.isoformat(),
        "semana_anterior": (d1 - timedelta(days=7)).isoformat(),
        "semana_siguiente": (d1 + timedelta(days=7)).isoformat(),
        "kpi_total_inasist": total_hist_inasist,
        "kpi_semana_inasist": semana_inasist,
        "kpi_pct_mes": pct_mes,
    }
    return render(request, "atleta/asistencia_semana.html", ctx)

# ================== PLANIFICACIÓN (semana) ==================
@role_required(Usuario.Tipo.ATLE)
def planificacion_semana(request):
    from datetime import datetime, timedelta
    raw = (request.GET.get("semana") or "").strip()
    try:
        dia = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        dia = timezone.localdate()
    d1, d2 = dia - timedelta(days=dia.weekday()), dia + timedelta(days=(6 - dia.weekday()))

    # Obtener los cursos donde está inscrito el atleta
    ins = Inscripcion.objects.filter(atleta__usuario=request.user)
    cursos_ids = list(ins.values_list("curso_id", flat=True))

    planes = Planificacion.objects.select_related("curso", "curso__sede", "curso__disciplina") \
        .filter(curso_id__in=cursos_ids, semana__range=(d1, d2)) \
        .order_by("curso__nombre")

    ctx = {
        "items": planes,
        "desde": d1, "hasta": d2,
        "semana": d1.isoformat(),
        "semana_anterior": (d1 - timedelta(days=7)).isoformat(),
        "semana_siguiente": (d1 + timedelta(days=7)).isoformat(),
    }
    return render(request, "atleta/planificacion_semana.html", ctx)

# ================== DOCUMENTOS / PROTOCOLOS ==================
@role_required(Usuario.Tipo.ATLE)
def documentos_protocolos(request):
    # Puedes rellenar con enlaces a PDFs, o a Comunicado con tipo "Protocolo"
    return render(request, "atleta/documentos_protocolos.html")

# ================== CAMBIAR PASSWORD (con correo obligatorio) ==================
@role_required(Usuario.Tipo.ATLE)
def cambiar_password(request):
    if request.method == "POST":
        pwd_old = request.POST.get("pwd_old", "")
        pwd1 = request.POST.get("pwd1", "")
        pwd2 = request.POST.get("pwd2", "")
        email = (request.POST.get("email") or "").strip()

        # exigir email si el usuario no tiene
        if not request.user.email and not email:
            messages.error(request, "Debes registrar un correo electrónico para cambiar tu contraseña.")
            return render(request, "atleta/../../templates/usuarios/cambiar_password.html")

        if pwd1 != pwd2:
            messages.error(request, "La nueva contraseña no coincide.")
            return render(request, "atleta/../../templates/usuarios/cambiar_password.html")

        # validar contraseña actual
        if not request.user.check_password(pwd_old):
            messages.error(request, "Tu contraseña actual no es correcta.")
            return render(request, "atleta/../../templates/usuarios/cambiar_password.html")

        # validadores de Django
        try:
            validate_password(pwd1, user=request.user)
        except PwdValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return render(request, "atleta/../../templates/usuarios/cambiar_password.html")

        # guardar email si lo proporcionó
        if email and email != request.user.email:
            request.user.email = email

        request.user.set_password(pwd1)
        request.user.save(update_fields=["password", "email"])
        update_session_auth_hash(request, request.user)  # mantener sesión

        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("usuarios:panel_atleta")

    return render(request, "atleta/../../templates/usuarios/cambiar_password.html")

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
