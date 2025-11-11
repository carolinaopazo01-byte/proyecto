# applications/pmul/views_disponibilidad.py
from datetime import datetime, timedelta, date, time

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
from django.contrib import messages



def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _sunday(d: date) -> date:
    return _monday(d) + timedelta(days=6)

def _estudiante_de(request):
    rut_norm = normalizar_rut(getattr(request.user, "rut", "") or getattr(request.user, "username", ""))
    if not rut_norm:
        return None
    return (
        Estudiante.objects
        .only("id", "rut")                 # <= clave del fix
        .filter(rut__in=[rut_norm, formatear_rut(rut_norm)])
        .first()
    )


@login_required
def mis_slots(request):
    if getattr(request.user, "tipo_usuario", "") != "PMUL":
        return HttpResponseForbidden("Solo profesionales pueden ver esto.")
    slots = Disponibilidad.objects.filter(profesional=request.user).order_by("-inicio")
    return render(request, "pmul/slots_list.html", {"slots": slots})
@login_required
def slot_nuevo(request):
    """Crea una única franja horaria manual."""
    if getattr(request.user, "tipo_usuario", "") != "PMUL":
        return HttpResponseForbidden("Solo profesionales pueden crear franjas.")

    if request.method == "POST":
        # Recoger los datos directamente desde el formulario existente
        fecha_inicio_raw = request.POST.get("fecha_inicio")
        hora_inicio_raw = request.POST.get("hora_inicio_dia")
        hora_fin_raw = request.POST.get("hora_fin_dia")
        piso = request.POST.get("piso", "")
        notas = request.POST.get("notas", "")

        # Validaciones básicas
        if not fecha_inicio_raw or not hora_inicio_raw or not hora_fin_raw:
            messages.error(request, "Debes completar fecha y horario.")
            return render(request, "pmul/slots_bulk_form.html")

        try:
            fecha = date.fromisoformat(fecha_inicio_raw)
            hora_inicio = time.fromisoformat(hora_inicio_raw)
            hora_fin = time.fromisoformat(hora_fin_raw)
        except Exception:
            messages.error(request, "Formato de fecha u hora inválido.")
            return render(request, "pmul/slots_bulk_form.html")

        if hora_fin <= hora_inicio:
            messages.error(request, "La hora de término debe ser posterior al inicio.")
            return render(request, "pmul/slots_bulk_form.html")

        # Combinar fecha + horas
        inicio = datetime.combine(fecha, hora_inicio)
        fin = datetime.combine(fecha, hora_fin)

        # Crear franja
        try:
            s = Disponibilidad.objects.create(
                profesional=request.user,
                inicio=inicio,
                fin=fin,
                piso=piso,
                notas=notas,
                estado=Disponibilidad.Estado.LIBRE,
            )
            print("✅ Franja creada correctamente:", s.id)
            messages.success(request, "✅ Franja creada correctamente.")
            return redirect("pmul:slots_list")
        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")

    # GET normal: mostrar formulario
    return render(request, "pmul/slots_bulk_form.html")

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
    return render(request, "pmul/slots_bulk_form.html", {"form": form})
@login_required
def slots_bulk_new(request):
    """Genera automáticamente múltiples franjas horarias según parámetros del formulario."""
    if request.method == "POST":
        # Validar campos básicos
        fecha_inicio_raw = request.POST.get("fecha_inicio")
        fecha_fin_raw = request.POST.get("fecha_fin")
        dias_semana_raw = request.POST.getlist("dias_semana")

        # Si falta algo esencial, avisar
        if not fecha_inicio_raw or not fecha_fin_raw or not dias_semana_raw:
            messages.error(request, "Debes completar rango de fechas y días de la semana.")
            return render(request, "pmul/slots_bulk_form.html")

        # Convertir strings a tipos de Python
        try:
            fecha_inicio = date.fromisoformat(fecha_inicio_raw)
            fecha_fin = date.fromisoformat(fecha_fin_raw)
            dias_semana = [int(x) for x in dias_semana_raw]
            hora_inicio_dia = time.fromisoformat(request.POST.get("hora_inicio_dia"))
            hora_fin_dia = time.fromisoformat(request.POST.get("hora_fin_dia"))
            duracion_min = int(request.POST.get("duracion_min"))
            intervalo_min = int(request.POST.get("intervalo_min"))
        except Exception as e:
            messages.error(request, f"Error en los datos: {e}")
            return render(request, "pmul/slots_bulk_form.html")

        # Datos opcionales
        pausa_ini = request.POST.get("pausa_ini") or ""
        pausa_fin = request.POST.get("pausa_fin") or ""
        pausas = []
        if pausa_ini and pausa_fin:
            try:
                pausas = [(time.fromisoformat(pausa_ini), time.fromisoformat(pausa_fin))]
            except Exception:
                pausas = []
        piso = request.POST.get("piso", "")
        notas = request.POST.get("notas", "")

        # Llamar método del modelo para generar franjas
        try:
            creados, omitidos = Disponibilidad.generar_lote(
                profesional=request.user,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                dias_semana=dias_semana,
                hora_inicio_dia=hora_inicio_dia,
                hora_fin_dia=hora_fin_dia,
                duracion_min=duracion_min,
                intervalo_min=intervalo_min,
                pausas=pausas,
                piso=piso,
                notas=notas,
                estado=Disponibilidad.Estado.LIBRE,
            )
        except Exception as e:
            messages.error(request, f"Error al generar: {e}")
            return render(request, "pmul/slots_bulk_form.html")

        # Mostrar resultado
        if creados > 0:
            messages.success(request, f"✅ Se crearon {creados} franjas. Omitidas: {omitidos}")
        else:
            messages.warning(request, "⚠️ No se crearon nuevas franjas (posibles choques).")

        # Renderizar nuevamente la página con resumen
        return render(
            request,
            "pmul/slots_bulk_form.html",
            {"creados": creados, "omitidos": omitidos},
        )

    # GET inicial
    return render(request, "pmul/slots_bulk_form.html", {"creados": None, "omitidos": None})
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
        hijos = hijos_de_apoderado(request.user)  # queryset de Estudiante
        sel = request.GET.get("hijo") or request.POST.get("hijo")
        if sel:
            paciente = hijos.filter(pk=sel).first()
            if not paciente:
                return render(request, "pmul/reservar_result.html", {"ok": False, "msg": "Hijo no válido."})
        else:
            return render(request, "pmul/reservar_elegir_hijo.html", {"slot": slot, "hijos": hijos})
    else:
        rut_norm = normalizar_rut(getattr(request.user, "rut", "") or getattr(request.user, "username", ""))
        candidatos = [rut_norm, formatear_rut(rut_norm)] if rut_norm else []
        paciente = (
            Estudiante.objects
            .only("id", "rut")  # evita tocar columnas antiguas
            .filter(rut__in=candidatos)
            .first()
        )
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
            paciente=paciente,
            profesional=s.profesional,
            inicio=s.inicio,
            fin=s.fin,
            observacion="",
            estado="PEND",
        )
        s.estado = Disponibilidad.Estado.RESERVADA
        s.save(update_fields=["estado"])

    return render(request, "pmul/reservar_result.html", {"ok": True})

@login_required
def slot_editar(request, slot_id):
    """Permite editar una franja existente (solo del profesional dueño)."""
    slot = get_object_or_404(Disponibilidad, pk=slot_id)
    if slot.profesional != request.user:
        return HttpResponseForbidden("No tienes permiso para editar esta franja.")

    if request.method == "POST":
        fecha_raw = request.POST.get("fecha_inicio")
        hora_inicio_raw = request.POST.get("hora_inicio_dia")
        hora_fin_raw = request.POST.get("hora_fin_dia")
        piso = request.POST.get("piso", "")
        notas = request.POST.get("notas", "")

        try:
            fecha = date.fromisoformat(fecha_raw)
            hora_inicio = time.fromisoformat(hora_inicio_raw)
            hora_fin = time.fromisoformat(hora_fin_raw)
        except Exception:
            messages.error(request, "Formato de fecha u hora inválido.")
            return render(request, "pmul/slots_edit_form.html", {"slot": slot})

        inicio = datetime.combine(fecha, hora_inicio)
        fin = datetime.combine(fecha, hora_fin)
        if fin <= inicio:
            messages.error(request, "La hora de término debe ser posterior al inicio.")
            return render(request, "pmul/slots_edit_form.html", {"slot": slot})

        # Actualizar campos
        slot.inicio = inicio
        slot.fin = fin
        slot.piso = piso
        slot.notas = notas
        slot.save()

        messages.success(request, "✅ Franja actualizada correctamente.")
        return redirect("pmul:slots_list")

    return render(request, "pmul/slots_edit_form.html", {"slot": slot})

