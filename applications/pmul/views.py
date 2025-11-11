from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from applications.usuarios.decorators import role_required
from applications.usuarios.models import Usuario
from applications.core.models import Estudiante

from .forms import FichaClinicaForm
from .models import FichaClinica, FichaAdjunto


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


def _is_admin_or_coord(u):
    return getattr(u, "is_superuser", False) or getattr(u, "tipo_usuario", "") in (Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)

def _rut_variants(raw: str):
    raw = (raw or "").strip().upper()
    if not raw:
        return []
    rn = normalizar_rut(raw)                         # 12345678-9
    rf = formatear_rut(rn)                           # 12.345.678-9
    rns = rn.replace(".", "").replace("-", "")       # 123456789
    rraw = raw.replace(".", "").replace("-", "")     # 123456789
    seen, out = set(), []
    for v in (raw, rn, rf, rns, rraw):
        if v and v not in seen:
            out.append(v); seen.add(v)
    return out

def _get_estudiante_by_hint(est_id=None, rut=None):
    if est_id:
        try:
            return Estudiante.objects.select_related("curso").get(pk=est_id)
        except Estudiante.DoesNotExist:
            pass
    if rut:
        return (Estudiante.objects
                .select_related("curso")
                .filter(rut__in=_rut_variants(rut))
                .first())
    return None

def _can_view_ficha(u, f: FichaClinica):

    if not u.is_authenticated:
        return False
    if f.profesional_id == u.id or _is_admin_or_coord(u):
        return True

    if getattr(u, "tipo_usuario", "") == Usuario.Tipo.ATLE and getattr(u, "rut", None):
        est = _get_estudiante_by_hint(rut=u.rut)
        return bool(est and f.paciente_id == est.id)
    return False




@role_required("PMUL")
def fichas_list(request):
    qs = (FichaClinica.objects
          .filter(profesional=request.user)
          .select_related("paciente")
          .order_by("-fecha", "-id"))

    # Filtro opcional por paciente (?est=123)
    est_id = request.GET.get("est")
    if est_id:
        qs = qs.filter(paciente_id=est_id)

    return render(request, "pmul/fichas_list.html", {"items": qs[:300]})


@role_required("PMUL")
def ficha_new(request):
    # Preselección por hint en GET (?est=ID o ?rut=XXXXXXXXX)
    est_hint = _get_estudiante_by_hint(request.GET.get("est"), request.GET.get("rut"))

    if request.method == "POST":
        form = FichaClinicaForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.save(commit=False)
            f.profesional = request.user

            # Si el form no trae paciente, intentar fijarlo con hints de POST
            if not getattr(f, "paciente_id", None):
                est_post = _get_estudiante_by_hint(
                    request.POST.get("estudiante_id"),
                    request.POST.get("rut")
                )
                if est_post:
                    f.paciente = est_post
                elif est_hint:
                    f.paciente = est_hint

            if not f.paciente_id:
                messages.error(request, "Debes seleccionar el paciente (estudiante) antes de guardar.")
                return render(request, "pmul/ficha_form.html", {"form": form, "titulo": "Nueva ficha", "est": est_hint})

            f.save()

            # Adjuntos múltiples
            for up in request.FILES.getlist("adjuntos"):
                FichaAdjunto.objects.create(ficha=f, archivo=up, nombre=getattr(up, "name", ""))

            messages.success(request, "Ficha creada correctamente.")
            return redirect("pmul:ficha_detail", ficha_id=f.id)
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        initial = {}
        if est_hint:
            initial["paciente"] = est_hint.id
        form = FichaClinicaForm(initial=initial)

    return render(request, "pmul/ficha_form.html", {"form": form, "titulo": "Nueva ficha", "est": est_hint})


@role_required("PMUL")
def ficha_detail(request, ficha_id):
    f = get_object_or_404(FichaClinica.objects.select_related("paciente"), pk=ficha_id)
    if not (f.profesional_id == request.user.id or _is_admin_or_coord(request.user)):
        # Si lo prefieres, devuelve 403 en vez de 404
        raise Http404()
    return render(request, "pmul/ficha_detail.html", {"f": f})


@role_required("PMUL")
def ficha_toggle_publicacion(request, ficha_id):
    if request.method != "POST":
        raise Http404()
    f = get_object_or_404(FichaClinica, pk=ficha_id)
    if not (f.profesional_id == request.user.id or _is_admin_or_coord(request.user)):
        raise Http404()

    f.publicar_profesor    = bool(request.POST.get("publicar_profesor"))
    f.publicar_coordinador = bool(request.POST.get("publicar_coordinador"))
    f.publicar_admin       = bool(request.POST.get("publicar_admin"))
    f.save(update_fields=["publicar_profesor", "publicar_coordinador", "publicar_admin"])

    return redirect("pmul:ficha_detail", ficha_id=f.id)


@login_required
def ficha_descargar_adjunto(request, ficha_id, adj_id):
    adj = get_object_or_404(
        FichaAdjunto.objects.select_related("ficha", "ficha__paciente"),
        pk=adj_id, ficha_id=ficha_id
    )
    f = adj.ficha
    if not _can_view_ficha(request.user, f):
        raise Http404()

    nombre = adj.nombre or getattr(adj.archivo, "name", "adjunto")
    return FileResponse(adj.archivo.open("rb"), as_attachment=True, filename=nombre)


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