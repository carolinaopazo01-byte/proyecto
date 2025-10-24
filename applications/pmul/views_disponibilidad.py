from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.urls import reverse

from .models import Disponibilidad
from .forms import SlotForm, SlotRecurrenteForm
from .models import Cita  # tu modelo de agenda existente
from applications.apoderado.utils import hijos_de_apoderado  # ya lo tienes

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
