from datetime import date, datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.http import FileResponse, Http404
from django.utils import timezone

# Si tienes decorador de roles, úsalo; si no, el login_required queda OK
try:
    from applications.usuarios.decorators import role_required
except Exception:
    def role_required(*roles):
        # fallback simple
        def deco(fn):
            @login_required
            def _wrap(request, *a, **kw):
                return fn(request, *a, **kw)
            return _wrap
        return deco

from applications.core.models import Estudiante  # cambia si tu "paciente" se llama distinto
from .models import Cita, FichaClinica, FichaAdjunto, PISOS
from .forms import CitaForm, FichaClinicaForm, AdjuntoForm

def semana_lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())

def semana_domingo(d: date) -> date:
    return semana_lunes(d) + timedelta(days=6)

# -------- DASHBOARD
@role_required("PMUL")
def panel(request):
    hoy = timezone.localdate()
    ini = semana_lunes(hoy)
    fin = semana_domingo(hoy)

    citas_hoy = Cita.objects.filter(profesional=request.user, inicio__date=hoy).count()
    atendidas_semana = Cita.objects.filter(profesional=request.user, inicio__date__range=(ini, fin), estado="REAL").count()
    pendientes_reprog = Cita.objects.filter(profesional=request.user, inicio__date__range=(ini, fin), estado__in=["PEND", "REPROG"]).count()
    deportistas_activos = Estudiante.objects.filter(activo=True).count() if hasattr(Estudiante, "activo") else Estudiante.objects.count()

    return render(request, "pmul/panel.html", {
        "citas_hoy": citas_hoy,
        "atendidas_semana": atendidas_semana,
        "deportistas_activos": deportistas_activos,
        "pendientes_reprog": pendientes_reprog,
    })

# -------- AGENDA: listar
@role_required("PMUL")
def agenda(request):
    # filtros
    f_desde = request.GET.get("desde")
    f_hasta = request.GET.get("hasta")
    f_piso = request.GET.get("piso")
    f_estado = request.GET.get("estado")

    qs = Cita.objects.filter(profesional=request.user)

    if f_desde:
        try:
            d1 = datetime.strptime(f_desde, "%Y-%m-%d").date()
            qs = qs.filter(inicio__date__gte=d1)
        except ValueError:
            pass
    if f_hasta:
        try:
            d2 = datetime.strptime(f_hasta, "%Y-%m-%d").date()
            qs = qs.filter(inicio__date__lte=d2)
        except ValueError:
            pass
    if f_piso in {"1", "2"}:
        qs = qs.filter(piso=int(f_piso))
    if f_estado in {"PEND", "REAL", "REPROG", "CANC"}:
        qs = qs.filter(estado=f_estado)

    qs = qs.order_by("inicio")[:500]

    return render(request, "pmul/agenda.html", {
        "items": qs,
        "f_desde": f_desde or "",
        "f_hasta": f_hasta or "",
        "f_piso": f_piso or "",
        "f_estado": f_estado or "",
        "pisos": PISOS,
    })

# -------- AGENDA: crear / editar / cancelar / reprogramar
@role_required("PMUL")
def cita_new(request):
    if request.method == "POST":
        form = CitaForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("pmul:agenda")
    else:
        form = CitaForm(user=request.user)
    return render(request, "pmul/cita_form.html", {"form": form, "titulo": "Nueva cita"})

@role_required("PMUL")
def cita_edit(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id, profesional=request.user)
    if request.method == "POST":
        form = CitaForm(request.POST, instance=cita, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("pmul:agenda")
    else:
        # precargar fecha/hora en los widgets auxiliares
        initial = {
            "fecha": cita.inicio.date(),
            "hora_inicio": cita.inicio.time().replace(microsecond=0),
            "hora_fin": cita.fin.time().replace(microsecond=0) if cita.fin else None,
        }
        form = CitaForm(instance=cita, initial=initial, user=request.user)
    return render(request, "pmul/cita_form.html", {"form": form, "titulo": "Editar cita"})

@role_required("PMUL")
def cita_cancel(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id, profesional=request.user)
    cita.estado = "CANC"
    cita.save(update_fields=["estado"])
    return redirect("pmul:agenda")

@role_required("PMUL")
def cita_reprogramar(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id, profesional=request.user)
    # ejemplo simple: +1 día
    cita.inicio = cita.inicio + timedelta(days=1)
    cita.estado = "REPROG"
    cita.save(update_fields=["inicio", "estado"])
    return redirect("pmul:agenda")

# -------- FICHAS
@role_required("PMUL")
def fichas_list(request):
    qs = FichaClinica.objects.filter(profesional=request.user).select_related("paciente").order_by("-fecha")[:300]
    return render(request, "pmul/fichas_list.html", {"items": qs})

@role_required("PMUL")
def ficha_new(request):
    if request.method == "POST":
        form = FichaClinicaForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False)
            f.profesional = request.user
            f.save()
            # adjuntos
            for up in request.FILES.getlist("adjuntos"):
                FichaAdjunto.objects.create(ficha=f, archivo=up, nombre=up.name)
            return redirect("pmul:ficha_detail", ficha_id=f.id)
    else:
        form = FichaClinicaForm()
    return render(request, "pmul/ficha_form.html", {"form": form, "titulo": "Nueva ficha"})

@role_required("PMUL")
def ficha_detail(request, ficha_id):
    f = get_object_or_404(FichaClinica, pk=ficha_id, profesional=request.user)
    return render(request, "pmul/ficha_detail.html", {"f": f})

@role_required("PMUL")
def ficha_toggle_publicacion(request, ficha_id):
    if request.method != "POST":
        raise Http404()
    f = get_object_or_404(FichaClinica, pk=ficha_id, profesional=request.user)
    f.publicar_profesor = bool(request.POST.get("publicar_profesor"))
    f.publicar_coordinador = bool(request.POST.get("publicar_coordinador"))
    f.publicar_admin = bool(request.POST.get("publicar_admin"))
    f.save(update_fields=["publicar_profesor", "publicar_coordinador", "publicar_admin"])
    return redirect("pmul:ficha_detail", ficha_id=f.id)

@role_required("PMUL")
def ficha_descargar_adjunto(request, ficha_id, adj_id):
    adj = get_object_or_404(FichaAdjunto, pk=adj_id, ficha_id=ficha_id)
    return FileResponse(adj.archivo.open("rb"), as_attachment=True, filename=adj.nombre or adj.archivo.name)

# -------- REPORTES (esqueleto)
@role_required("PMUL")
def reportes(request):
    d1 = request.GET.get("desde")
    d2 = request.GET.get("hasta")
    try:
        desde = datetime.strptime(d1, "%Y-%m-%d").date() if d1 else semana_lunes(timezone.localdate())
        hasta = datetime.strptime(d2, "%Y-%m-%d").date() if d2 else semana_domingo(timezone.localdate())
    except ValueError:
        desde, hasta = semana_lunes(timezone.localdate()), semana_domingo(timezone.localdate())

    qs = Cita.objects.filter(profesional=request.user, inicio__date__range=(desde, hasta))
    data = {
        "total": qs.count(),
        "atendidas": qs.filter(estado="REAL").count(),
        "reprogramadas": qs.filter(estado="REPROG").count(),
        "canceladas": qs.filter(estado="CANC").count(),
        "pendientes": qs.filter(estado="PEND").count(),
    }
    return render(request, "pmul/reportes.html", {"desde": desde, "hasta": hasta, **data})
