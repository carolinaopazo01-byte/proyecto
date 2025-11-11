# applications/atleta/views.py
from datetime import date, datetime, timedelta

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password, ValidationError as PwdValidationError
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone

from applications.usuarios.decorators import role_required
from applications.usuarios.utils import normalizar_rut, formatear_rut
from applications.usuarios.models import Usuario

from applications.core.models import Estudiante, Curso, Planificacion
from applications.pmul.models import Disponibilidad, Cita, FichaClinica

from .models import AsistenciaAtleta, Clase, Inscripcion


# ----------------- helpers de semana -----------------
def _mon(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _sun(d: date) -> date:
    return _mon(d) + timedelta(days=6)


# ----------------- helper: Usuario -> Estudiante -----------------
def _get_estudiante_de_usuario(user):
    """
    Busca el Estudiante asociado al usuario (por RUT en varias variantes y/o email).
    """
    rut_user = (getattr(user, "rut", "") or "").strip()
    rut_variants = set()
    if rut_user:
        try:
            rn = normalizar_rut(rut_user)
            rut_variants.update({rn, formatear_rut(rn), rn.replace(".", ""), rn.replace("-", "")})
        except Exception:
            rut_variants.add(rut_user)

    filt = Q()
    if rut_variants:
        filt |= Q(rut__in=list(rut_variants))
    if getattr(user, "email", ""):
        filt |= Q(email=user.email)

    return (Estudiante.objects
            .select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")
            .prefetch_related("curso__horarios")
            .filter(filt)
            .first())



@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def mis_cursos(request):
    est = _get_estudiante_de_usuario(request.user)

    # Adaptar al template (espera items con .curso)
    items = []
    if est and getattr(est, "curso_id", None):
        class _Lite:
            pass
        lite = _Lite()
        lite.curso = est.curso
        items = [lite]

    return render(request, "atleta/mis_cursos.html", {"inscripciones": items})


# ================== FICHAS (ATLE) ==================
@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def mis_fichas(request):
    est = _get_estudiante_de_usuario(request.user)
    if not est:
        messages.warning(request, "No encontramos tu ficha de estudiante asociada a tu usuario.")
        return redirect("atleta:panel")  # ajusta si tu nombre de panel es otro

    fichas = (FichaClinica.objects
              .filter(paciente=est)
              .select_related("profesional", "paciente")
              .prefetch_related("adjuntos")
              .order_by("-fecha", "-id"))
    return render(request, "atleta/mis_fichas.html", {"items": fichas, "est": est})


# ================== HORAS DISPONIBLES / RESERVA ==================
@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def horas_disponibles(request):
    """
    Lista de slots LIBRES futuros. Filtros opcionales:
      - esp=NUT/KIN/...
      - prof=ID de usuario PMUL
      - desde=YYYY-MM-DD
    """
    qs = (Disponibilidad.objects
          .select_related("profesional")
          .filter(estado=Disponibilidad.Estado.LIBRE, inicio__gte=timezone.now())
          .order_by("inicio"))

    esp = (request.GET.get("esp") or "").upper().strip()
    if esp:
        qs = qs.filter(profesional__perfil_pmul__especialidad=esp)

    prof_id = request.GET.get("prof")
    if prof_id and prof_id.isdigit():
        qs = qs.filter(profesional_id=int(prof_id))

    desde = request.GET.get("desde")
    if desde:
        try:
            d = datetime.strptime(desde, "%Y-%m-%d").date()
            qs = qs.filter(inicio__date__gte=d)
        except Exception:
            pass

    items = qs[:300]
    return render(request, "atleta/horas_disponibles.html", {"items": items})


@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["POST"])
def reservar_hora(request, slot_id: int):
    """
    Reserva un slot LIBRE creando Cita y cambiando el slot a RESERVADA.
    """
    est = _get_estudiante_de_usuario(request.user)
    if not est:
        messages.error(request, "No encontramos tu ficha de estudiante; no puedes reservar.")
        return redirect("atleta:horas_disponibles")

    with transaction.atomic():
        slot = (Disponibilidad.objects
                .select_for_update()
                .select_related("profesional")
                .filter(pk=slot_id)
                .first())
        if not slot:
            messages.error(request, "El bloque seleccionado ya no existe.")
            return redirect("atleta:horas_disponibles")

        if slot.estado != Disponibilidad.Estado.LIBRE:
            messages.error(request, "Ese bloque ya fue tomado.")
            return redirect("atleta:horas_disponibles")

        cita = Cita(
            paciente=est,
            profesional=slot.profesional,
            inicio=slot.inicio,
            fin=slot.fin,
            observacion="",
        )
        # Validaciones de negocio (no en pasado, una por día, no solape profesional)
        cita.full_clean()
        cita.save()

        slot.estado = Disponibilidad.Estado.RESERVADA
        slot.save(update_fields=["estado"])

    messages.success(request, "¡Tu hora fue reservada con éxito!")
    return redirect("atleta:mis_citas")


@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def mis_citas(request):
    est = _get_estudiante_de_usuario(request.user)
    if not est:
        messages.warning(request, "No encontramos tu ficha de estudiante asociada a tu usuario.")
        return redirect("atleta:panel")

    citas = (Cita.objects
             .select_related("profesional", "paciente")
             .filter(paciente=est)
             .order_by("-inicio"))
    return render(request, "atleta/mis_citas.html", {"items": citas, "ahora": timezone.now()})


@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["POST"])
def cita_cancelar(request, cita_id: int):
    """
    Cancela la cita del atleta autenticado y, si corresponde, libera el slot RESERVADA.
    """
    est = _get_estudiante_de_usuario(request.user)
    if not est:
        messages.error(request, "No se pudo validar tu ficha de estudiante.")
        return redirect("atleta:mis_citas")

    with transaction.atomic():
        cita = get_object_or_404(Cita.objects.select_for_update(), pk=cita_id, paciente=est)

        if cita.estado == "CANC":
            messages.info(request, "La cita ya estaba cancelada.")
            return redirect("atleta:mis_citas")

        cita.estado = "CANC"
        cita.save(update_fields=["estado"])

        slot = (Disponibilidad.objects
                .select_for_update()
                .filter(
                    profesional=cita.profesional,
                    inicio=cita.inicio,
                    fin=cita.fin,
                    estado=Disponibilidad.Estado.RESERVADA,
                ).first())
        if slot:
            slot.estado = Disponibilidad.Estado.LIBRE
            slot.save(update_fields=["estado"])

    messages.success(request, "Cita cancelada.")
    return redirect("atleta:mis_citas")


# ================== ASISTENCIA (vista semanal + KPIs) ==================
@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def asistencia_semana(request):
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
@require_http_methods(["GET"])
def planificacion_semana(request):
    raw = (request.GET.get("semana") or "").strip()
    try:
        dia = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        dia = timezone.localdate()
    d1, d2 = dia - timedelta(days=dia.weekday()), dia + timedelta(days=(6 - dia.weekday()))

    ins = Inscripcion.objects.filter(atleta__usuario=request.user)
    cursos_ids = list(ins.values_list("curso_id", flat=True))

    planes = (Planificacion.objects
              .select_related("curso", "curso__sede", "curso__disciplina")
              .filter(curso_id__in=cursos_ids, semana__range=(d1, d2))
              .order_by("curso__nombre"))

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
@require_http_methods(["GET"])
def documentos_protocolos(request):
    return render(request, "atleta/documentos_protocolos.html")


# ================== CAMBIAR PASSWORD (con correo obligatorio) ==================
@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET", "POST"])
def cambiar_password(request):
    template = "usuarios/cambiar_password.html"  # ruta correcta del template
    if request.method == "POST":
        pwd_old = request.POST.get("pwd_old", "")
        pwd1 = request.POST.get("pwd1", "")
        pwd2 = request.POST.get("pwd2", "")
        email = (request.POST.get("email") or "").strip()

        if not request.user.email and not email:
            messages.error(request, "Debes registrar un correo electrónico para cambiar tu contraseña.")
            return render(request, template)

        if pwd1 != pwd2:
            messages.error(request, "La nueva contraseña no coincide.")
            return render(request, template)

        if not request.user.check_password(pwd_old):
            messages.error(request, "Tu contraseña actual no es correcta.")
            return render(request, template)

        try:
            validate_password(pwd1, user=request.user)
        except PwdValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return render(request, template)

        if email and email != request.user.email:
            request.user.email = email

        request.user.set_password(pwd1)
        request.user.save(update_fields=["password", "email"])
        update_session_auth_hash(request, request.user)

        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("usuarios:panel_atleta")

    return render(request, template)


# ------- Agenda del Equipo Multidisciplinario (placeholder) -------
@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def agenda_disponible(request):
    return HttpResponse("ATLETA / Agenda disponible (GET) -> ver horarios y citas disponibles")


# ------- Crear Cita (placeholder) -------
@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def cita_crear(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Cita - CREAR (POST) -> agendada OK")
    return HttpResponse("ATLETA / Cita - FORMULARIO CREAR (GET)")


# ------- Proceso de Ingreso a Alto Rendimiento (placeholder) -------
@role_required(Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def proceso_ingreso_alto_rendimiento(request):
    if request.method == "POST":
        return HttpResponse("ATLETA / Proceso Ingreso AR (POST) -> paso guardado")
    return HttpResponse("ATLETA / Proceso Ingreso AR (GET) -> ver pasos/ficha/documentos")



@role_required(Usuario.Tipo.ATLE)
@require_http_methods(["GET"])
def panel(request):

    fnac = getattr(request.user, "fecha_nacimiento", None)
    if fnac:
        edad = (date.today() - fnac).days // 365
        if edad < 18:
            messages.error(request, "Acceso restringido a mayores de edad.")
            return redirect("usuarios:logout")
    return render(request, "atleta/panel.html", {"titulo": "Panel del Atleta"})
