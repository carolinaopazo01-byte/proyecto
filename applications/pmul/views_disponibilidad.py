from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Disponibilidad, Cita

from .forms import SlotForm, SlotRecurrenteForm

from applications.apoderado.utils import hijos_de_apoderado  # ya lo tienes
from applications.core.models import Estudiante
from applications.usuarios.utils import role_required

from datetime import datetime, timedelta, date

#-------------------------

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _sunday(d: date) -> date:
    return _monday(d) + timedelta(days=6)

# ---------- LISTADO PARA ATLETA/APODERADO (filtrado por semana) ----------
@login_required
def reservar_listado(request):
    # 1) Resolver el día de referencia
    raw = (request.GET.get("semana") or "").strip()
    if raw:
        try:
            dia = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    desde = _monday(dia)
    hasta = _sunday(dia)

    # 2) (Opcional) filtro por especialidad
    subrol = (request.GET.get("subrol") or "").upper().strip()

    qs = Disponibilidad.objects.filter(
        estado=Disponibilidad.Estado.LIBRE,
        inicio__date__range=(desde, hasta),
    ).select_related("profesional").order_by("inicio")

    if subrol:
        qs = qs.filter(profesional__perfil_pmul__especialidad=subrol)

    ctx = {
        "slots": qs,
        "desde": desde,
        "hasta": hasta,
        "semana": desde.isoformat(),  # valor para el <input type=date>
        "semana_anterior": (desde - timedelta(days=7)).isoformat(),
        "semana_siguiente": (desde + timedelta(days=7)).isoformat(),
    }
    return render(request, "pmul/reservar_listado.html", ctx)

# ---------- CONFIRMAR/CREAR LA CITA DESDE UNA FRANJA ----------
@login_required
@transaction.atomic
def reservar_confirmar(request, slot_id: int):
    rol = (getattr(request.user, "tipo_usuario", "") or "").upper()
    if rol not in {"ATLE", "APOD", "COORD", "ADMIN"}:
        return HttpResponseForbidden("No tienes permiso para reservar horas.")

    slot = get_object_or_404(Disponibilidad, pk=slot_id)

    # Validaciones básicas
    if slot.estado != Disponibilidad.Estado.LIBRE:
        return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "El cupo ya no está disponible."})
    if slot.inicio < timezone.now():
        return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "No puedes reservar en el pasado."})

    # ¿Qué estudiante/paciente asociar a la reserva?
    # Intento 1: estudiante vinculado por RUT del usuario (campo 'rut' en Estudiante)
    est = None
    # Busca por RUT (con y sin puntos)
    from applications.usuarios.utils import normalizar_rut, formatear_rut
    rut_user = normalizar_rut(getattr(request.user, "rut", "") or getattr(request.user, "username", ""))
    if rut_user:
        est = Estudiante.objects.filter(rut__in=[rut_user, formatear_rut(rut_user)]).first()

    # Si eres apoderado podrías elegir a cuál hijo reservar; por ahora,
    # si no se encuentra, muestra error claro.
    if not est:
        return render(
            request,
            "pmul/reservar_result.html",
            {"ok": False, "msg": "No encontré tu ficha de Estudiante para asociar la reserva."},
        )

    # Crear Cita y bloquear la franja
    Cita.objects.create(
        paciente=est,
        profesional=slot.profesional,
        inicio=slot.inicio,
        fin=slot.fin,
        observacion="",  # opcional
        estado="PEND",
    )
    slot.estado = Disponibilidad.Estado.RESERVADA
    slot.save(update_fields=["estado"])

    return render(request, "pmul/reservar_result.html", {"ok": True})

# ---------- PROFESIONAL: listar / crear / bulk ----------

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
            items = form.generar_slots(request.user) or []  # 👈 evita None
            for s in items:
                # no publicar si se solapa con otra del mismo profesional
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


# ---------- APODERADO / ATLETA: ver y reservar ----------

@login_required
def reservar_listado(request):
    """
    Lista de slots LIBRES de hoy en adelante.
    Si user es APOD: puede elegir por cuál hijo reserva.
    Si user es ATLE: reserva para sí.
    """
    hoy = timezone.now()
    qs = Disponibilidad.objects.filter(
        estado=Disponibilidad.Estado.LIBRE, inicio__gte=hoy
    ).select_related("profesional").order_by("inicio")

    # filtros opcionales: especialidad/subrol
    subrol = request.GET.get("subrol")  # KINE|PSIC|NUTR|TENS
    if subrol:
        qs = qs.filter(profesional__equipo_rol=subrol)

    return render(request, "pmul/reservar_listado.html", {"slots": qs})

@login_required
def reservar_confirmar(request, slot_id):
    slot = get_object_or_404(Disponibilidad, pk=slot_id, estado=Disponibilidad.Estado.LIBRE)
    user = request.user

    # elegir paciente: si es APOD, escoger hijo; si es ATLE, es él mismo
    paciente = None
    if getattr(user, "tipo_usuario", "") == "APOD":
        hijos = hijos_de_apoderado(user)
        sel = request.GET.get("hijo") or request.POST.get("hijo")
        if sel:
            paciente = hijos.filter(pk=sel).first()
        else:
            # pantalla para elegir hijo
            return render(request, "pmul/reservar_elegir_hijo.html", {"slot": slot, "hijos": hijos})
    else:
        # atleta mayor de edad u otro rol autorizado
        paciente = getattr(user, "estudiante", None) or user  # ajusta a tu modelo de atleta

    if request.method == "POST":
        # crear Cita de forma atómica y marcar slot como RESERVADA
        with transaction.atomic():
            s = Disponibilidad.objects.select_for_update().get(pk=slot.pk)
            if s.estado != Disponibilidad.Estado.LIBRE:
                return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "El cupo ya no está disponible."})
            # crear Cita (ajusta campos a tu modelo real)
            Cita.objects.create(
                profesional=s.profesional,
                paciente=paciente,
                inicio=s.inicio,
                fin=s.fin,
                piso=s.piso,
                estado="PEND",  # pendiente
                origen="RESERVA",  # opcional para auditar
            )
            s.estado = Disponibilidad.Estado.RESERVADA
            s.save(update_fields=["estado"])
        return render(request, "pmul/reservar_result.html", {"ok": True})
    return render(request, "pmul/reservar_confirmar.html", {"slot": slot, "paciente": paciente})
