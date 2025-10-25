# applications/atleta/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_http_methods

from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario
from applications.core.models import Estudiante
from .models import Clase, AsistenciaAtleta, Atleta
from .forms import AsistenciaFilaForm, InvitadoForm

@role_required(Usuario.Tipo.PROF)
def prof_panel(request):
    return render(request, "atleta/prof_panel.html")

@role_required(Usuario.Tipo.PROF)
def prof_clases(request):
    clases = (
        Clase.objects
        .select_related("sede_deporte__sede", "sede_deporte__deporte", "profesor")
        .filter(profesor=request.user)
        .order_by("-fecha", "hora_inicio")
    )
    return render(request, "atleta/prof_clases.html", {"clases": clases})

# ---------- Tomar asistencia ----------
@role_required(Usuario.Tipo.PROF)
@require_http_methods(["GET","POST"])
def prof_tomar_asistencia(request, clase_id: int):
    clase = get_object_or_404(
        Clase.objects.select_related("sede_deporte__sede","sede_deporte__deporte","profesor"),
        pk=clase_id, profesor=request.user
    )

    # 1) Base de inscritos:
    # Si tienes Inscripcion, úsala aquí. Como base mínima, tomamos estudiantes
    # del mismo curso/disciplina/sede si aplica; o bien el campo que uses.
    candidatos = (
        Atleta.objects
        .select_related("usuario")
        .all()
    )

    # Excluir quienes tengan ≥3 faltas injustificadas consecutivas
    candidatos = [a for a in candidatos if getattr(a, "faltas_consecutivas", 0) < 3]

    # Mapea atleta -> registro de asistencia existente (si ya se marcó)
    existentes = {r.atleta_id: r for r in AsistenciaAtleta.objects.filter(clase=clase, atleta__in=candidatos)}

    if request.method == "POST":
        # Procesa líneas
        filas = []
        for key in request.POST:
            if key.startswith("row-") and key.endswith("-id"):
                _, idx, _ = key.split("-")
                atleta_id = int(request.POST.get(f"row-{idx}-id"))
                presente = bool(request.POST.get(f"row-{idx}-presente"))
                justificada = bool(request.POST.get(f"row-{idx}-justificada"))
                obs = (request.POST.get(f"row-{idx}-observaciones") or "").strip()
                filas.append((atleta_id, presente, justificada, obs))

        with transaction.atomic():
            for atleta_id, presente, justificada, obs in filas:
                reg = existentes.get(atleta_id)
                if not reg:
                    reg = AsistenciaAtleta(clase=clase, atleta_id=atleta_id)
                reg.presente = presente
                reg.justificada = justificada
                reg.observaciones = obs
                reg.save()

        messages.success(request, "Asistencia guardada.")
        return redirect("atleta:prof_tomar_asistencia", clase_id=clase.id)

    # GET -> arma estructura para la tabla
    filas = []
    for i, a in enumerate(candidatos, start=1):
        reg = existentes.get(a.id)
        filas.append({
            "idx": i,
            "atleta": a,
            "presente": bool(reg and reg.presente),
            "justificada": bool(reg and reg.justificada),
            "observaciones": getattr(reg, "observaciones", ""),
        })

    invitados = AsistenciaAtleta.objects.filter(clase=clase, atleta__isnull=True).order_by("creado")
    invitado_form = InvitadoForm()

    return render(request, "atleta/prof_tomar_asistencia.html", {
        "clase": clase,
        "filas": filas,
        "invitados": invitados,
        "invitado_form": invitado_form,
    })

# ---------- Levantar cupo (reinicia faltas y marca presente)
@role_required(Usuario.Tipo.PROF)
@require_http_methods(["POST"])
def prof_levantar_cupo(request, clase_id: int, atleta_id: int):
    clase = get_object_or_404(Clase, pk=clase_id, profesor=request.user)
    at = get_object_or_404(Atleta, pk=atleta_id)
    with transaction.atomic():
        # marca presente para esta clase
        reg, _ = AsistenciaAtleta.objects.get_or_create(clase=clase, atleta=at)
        reg.presente = True
        reg.justificada = False
        reg.save()
        # reinicia conteo
        if getattr(at, "faltas_consecutivas", 0) >= 3:
            at.faltas_consecutivas = 0
            at.save(update_fields=["faltas_consecutivas"])
    messages.success(request, f"Levantado el cupo de {at}.")
    return redirect("atleta:prof_tomar_asistencia", clase_id=clase.id)

# ---------- Agregar invitado/sobre-cupo ----------
@role_required(Usuario.Tipo.PROF)
@require_http_methods(["POST"])
def prof_agregar_invitado(request, clase_id: int):
    clase = get_object_or_404(Clase, pk=clase_id, profesor=request.user)
    form = InvitadoForm(request.POST)
    if form.is_valid():
        inv = form.save(commit=False)
        inv.clase = clase
        inv.sobre_cupo = True
        inv.presente = True
        inv.save()
        messages.success(request, "Invitado agregado como sobre-cupo.")
    else:
        messages.error(request, "Revisa los datos del invitado.")
    return redirect("atleta:prof_tomar_asistencia", clase_id=clase.id)

@role_required(Usuario.Tipo.ATLE)
def panel_atleta(request):
    return render(request, "atleta/panel.html")

@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def agenda_disponible(request):
    # Redirige a la lista de slots libres del módulo PMUL
    return redirect("pmul:reservar_listado")


@role_required(Usuario.Tipo.ATLE, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def cita_crear(request):
    return HttpResponse("ATLETA / (placeholder) crear cita")


@role_required(Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def proceso_ingreso_alto_rendimiento(request):
    return HttpResponse("ATLETA / Proceso Ingreso AR (placeholder)")
