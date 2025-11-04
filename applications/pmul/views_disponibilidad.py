# applications/pmul/views_disponibilidad.py
from datetime import datetime, timedelta, date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Disponibilidad, Cita
from .forms import SlotForm, SlotRecurrenteForm

from applications.apoderado.utils import hijos_de_apoderado
from applications.core.models import Estudiante
from applications.usuarios.utils import normalizar_rut, formatear_rut


# ----------------- helpers de semana -----------------
def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _sunday(d: date) -> date:
    return _monday(d) + timedelta(days=6)

def _estudiante_de(request):
    """Busca la ficha Estudiante del usuario por RUT (con y sin puntos)."""
    rut_norm = normalizar_rut(getattr(request.user, "rut", "") or getattr(request.user, "username", ""))
    if not rut_norm:
        return None
    return Estudiante.objects.filter(rut__in=[rut_norm, formatear_rut(rut_norm)]).first()

# ================== PROFESIONAL (PMUL): mis slots ==================
@login_required
def mis_slots(request):
    if getattr(request.user, "tipo_usuario", "") != "PMUL":
        return HttpResponseForbidden("Solo profesionales pueden ver esto.")
    slots = Disponibilidad.objects.filter(profesional=request.user).order_by("-inicio")
    return render(request, "pmul/slots_list.html", {"slots": slots})


@login_required
def slot_nuevo(request):
    if getattr(request.user, "tipo_usuario", "") != "PMUL":
        return HttpResponseForbidden("Solo profesionales pueden crear slots.")
    if request.method == "POST":
        form = SlotForm(request.POST)
        if form.is_valid():
            s = form.save(commit=False)
            s.profesional = request.user
            s.save()
            return redirect("pmul:slots_list")
    else:
        form = SlotForm()
    return render(request, "pmul/slots_form.html", {"form": form})


@login_required
def slot_bulk(request):
    if getattr(request.user, "tipo_usuario", "") != "PMUL":
        return HttpResponseForbidden("Solo profesionales.")
    if request.method == "POST":
        form = SlotRecurrenteForm(request.POST)
        if form.is_valid():
            items = form.generar_slots(request.user) or []
            for s in items:
                # evitar solapes con slots del mismo profesional
                choque = Disponibilidad.objects.filter(
                    profesional=request.user,
                    inicio__lt=s.fin, fin__gt=s.inicio,
                ).exists()
                if not choque:
                    s.save()
            return redirect("pmul:slots_list")
    else:
        form = SlotRecurrenteForm()
    return render(request, "pmul/slot_bulk_form.html", {"form": form})


@login_required
def slot_cancelar(request, slot_id):
    s = get_object_or_404(Disponibilidad, pk=slot_id)
    if s.profesional != request.user:
        return HttpResponseForbidden("No perteneces a este slot.")
    s.estado = Disponibilidad.Estado.CANCELADA
    s.save(update_fields=["estado"])
    return redirect("pmul:slots_list")


# ================== ATLETA / APODERADO: ver y reservar ==================
@login_required
def reservar_listado(request):
    """
    Lista semanal de slots LIBRES. Navegación por semana y banner con próxima cita.
    """
    # 1) Día de referencia (param ?semana=YYYY-MM-DD) o hoy
    raw = (request.GET.get("semana") or "").strip()
    try:
        dia = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        dia = timezone.localdate()

    desde, hasta = _monday(dia), _sunday(dia)

    # 2) Próxima cita del atleta (si aplica)
    proxima_cita = None
    if (getattr(request.user, "tipo_usuario", "") or "").upper() == "ATLE":
        est = _estudiante_de(request)
        if est:
            proxima_cita = (
                Cita.objects
                .filter(paciente=est, inicio__gte=timezone.now(), estado__in=["PEND", "CONF"])
                .select_related("profesional")
                .order_by("inicio")
                .first()
            )

    # 3) QS semanal de slots (con filtro opcional por especialidad)
    subrol = (request.GET.get("subrol") or "").upper().strip()
    qs = (
        Disponibilidad.objects
        .filter(estado=Disponibilidad.Estado.LIBRE, inicio__date__range=(desde, hasta))
        .select_related("profesional")
        .order_by("inicio")
    )
    if subrol:
        qs = qs.filter(profesional__perfil_pmul__especialidad=subrol)

    # 4) Contexto
    ctx = {
        "slots": qs,
        "desde": desde, "hasta": hasta,
        "semana": desde.isoformat(),
        "semana_anterior": (desde - timedelta(days=7)).isoformat(),
        "semana_siguiente": (desde + timedelta(days=7)).isoformat(),
        "proxima_cita": proxima_cita,
    }
    return render(request, "pmul/reservar_listado.html", ctx)

@login_required
@transaction.atomic
def reservar_confirmar(request, slot_id: int):
    """
    Confirma la reserva para un Estudiante (paciente).
    - ATLE: se busca su ficha Estudiante por RUT.
    - APOD: debe elegir a cuál hijo (fichas Estudiante).
    """
    rol = (getattr(request.user, "tipo_usuario", "") or "").upper()
    if rol not in {"ATLE", "APOD", "COORD", "ADMIN"}:
        return HttpResponseForbidden("No tienes permiso para reservar horas.")

    slot = get_object_or_404(Disponibilidad, pk=slot_id)

    # Validaciones básicas de la franja
    if slot.estado != Disponibilidad.Estado.LIBRE:
        return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "El cupo ya no está disponible."})
    if slot.inicio < timezone.now():
        return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "No puedes reservar en el pasado."})

    # Resolver PACIENTE (siempre un Estudiante)
    paciente = None

    if rol == "APOD":
        # Apoderado: elegir hijo
        hijos = hijos_de_apoderado(request.user)  # queryset de Estudiante
        sel = request.GET.get("hijo") or request.POST.get("hijo")
        if sel:
            paciente = hijos.filter(pk=sel).first()
            if not paciente:
                return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "Hijo no válido."})
        else:
            # pantalla para elegir hijo
            return render(request, "pmul/reservar_elegir_hijo.html", {"slot": slot, "hijos": hijos})

    else:
        # ATLE (u otro rol autorizado): buscar Estudiante por RUT del usuario
        rut_norm = normalizar_rut(getattr(request.user, "rut", "") or getattr(request.user, "username", ""))
        candidatos = [rut_norm, formatear_rut(rut_norm)] if rut_norm else []
        paciente = Estudiante.objects.filter(rut__in=candidatos).first()
        if not paciente:
            return render(
                request, "pmul/reservar_result.html",
                {"ok": False, "msg": "No encontré tu ficha de Estudiante para asociar la reserva. Avísale a coordinación."},
            )

    # Crear cita y bloquear slot de forma atómica
    with transaction.atomic():
        s = Disponibilidad.objects.select_for_update().get(pk=slot.pk)
        if s.estado != Disponibilidad.Estado.LIBRE:
            return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "El cupo ya no está disponible."})

        Cita.objects.create(
            paciente=paciente,               # Estudiante (no Usuario)
            profesional=s.profesional,
            inicio=s.inicio,
            fin=s.fin,
            observacion="",
            estado="PEND",
        )
        s.estado = Disponibilidad.Estado.RESERVADA
        s.save(update_fields=["estado"])

    return render(request, "pmul/reservar_result.html", {"ok": True})
