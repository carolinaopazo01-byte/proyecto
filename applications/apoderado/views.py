# applications/apoderado/views.py
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.apps import apps
from .utils import hijos_de_apoderado, porcentaje_asistencia_semana, proxima_clase_de, proximas_citas_para

@login_required
def dashboard(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)
    hijo = hijos.first() if hasattr(hijos, "first") else None

    # tarjetas (si hay al menos un hijo)
    asistencia_pct = porcentaje_asistencia_semana(hijo) if hijo else None
    proxima_clase = proxima_clase_de(hijo) if hijo else None
    citas = proximas_citas_para(hijo) if hijo else 0

    ctx = {
        "apoderado": apoderado,
        "hijos": hijos,
        "hijo": hijo,
        "asistencia_pct": asistencia_pct,
        "proxima_clase": proxima_clase,
        "citas": citas,
    }
    return render(request, "apoderado/dashboard.html", ctx)

@login_required
def asistencia(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)

    # hijo seleccionado (si hay varios)
    sel = request.GET.get("hijo")
    if sel and hasattr(hijos, "filter"):
        hijo = hijos.filter(pk=sel).first()
    else:
        hijo = hijos.first() if hasattr(hijos, "first") else None

    # 🔐 cargar el modelo de asistencia de forma segura (sin LookupError)
    Asis = (
        get_model("core.AsistenciaAtleta")
        or get_model("core.AsistenciaAlumno")
        or get_model("atleta.Asistencia")
        or get_model("asista.AsistenciaAlumno")   # 👈 agrega tu app real si se llama "asista"
    )

    items = []
    if Asis and hijo:
        hoy = timezone.localdate()
        ini = hoy.replace(day=1)
        fin = (ini + timedelta(days=40)).replace(day=1) - timedelta(days=1)

        # detectar el nombre del FK hacia el estudiante dinámicamente
        fk_name = None
        for f in Asis._meta.fields:
            if f.is_relation and getattr(f.related_model, "_meta", None) and f.related_model == hijo._meta.model:
                fk_name = f.name
                break

        if fk_name:
            qs = Asis.objects.filter(**{fk_name: hijo, "fecha__range": (ini, fin)}).order_by("fecha")
            items = list(qs)

    return render(request, "apoderado/asistencia.html", {
        "hijos": hijos, "hijo": hijo, "items": items
    })

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
        # si hay relación curso-estudiante, filtra por su(s) curso(s)
        if Curso and "curso" in [f.name for f in Plan._meta.fields]:
            # intentar obtener curso del atleta (ver util)
            prox = proxima_clase_de(hijo)
            curso = prox["curso"] if prox else None
            if curso:
                qs = qs.filter(curso=curso)
        items = list(qs.order_by("curso__nombre" if Curso else "id"))

    return render(request, "apoderado/planificacion.html", {
        "hijos": hijos, "hijo": hijo, "items": items
    })

@login_required
def evaluaciones(request):
    apoderado = request.user
    hijos = hijos_de_apoderado(apoderado)
    hijo = hijos.first() if hasattr(hijos, "first") else None

    # fichas PMUL visibles al profesor/atleta (asumimos publicar_profesor True)
    Ficha = apps.get_model("pmul", "FichaClinica", require_ready=False)
    items = []
    if Ficha and hijo:
        items = list(Ficha.objects.filter(paciente=hijo, publicar_profesor=True).order_by("-fecha")[:200])
    return render(request, "apoderado/evaluaciones.html", {"hijos": hijos, "hijo": hijo, "items": items})

@login_required
def comunicados(request):
    # Si tienes un modelo Comunicado en core, lo listamos:
    Com = apps.get_model("core", "Comunicado", require_ready=False)
    items = list(Com.objects.order_by("-creado")[:200]) if Com else []
    return render(request, "apoderado/comunicados.html", {"items": items})

@login_required
def protocolos(request):
    # Si tienes tabla de documentos/protocolos en core:
    Doc = (apps.get_model("core", "Documento") or apps.get_model("core", "Protocolo"))
    items = list(Doc.objects.order_by("-id")[:200]) if Doc else []
    return render(request, "apoderado/protocolos.html", {"items": items})
