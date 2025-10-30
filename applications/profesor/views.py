# applications/profesor/views.py
from datetime import datetime, timedelta
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from io import BytesIO
import qrcode
from qrcode.constants import ERROR_CORRECT_M

from applications.core.models import Sede, Estudiante

from .models import AsistenciaProfesor

from .forms import AlumnoTemporalForm

#########################

def _es_prof(user) -> bool:
    return (getattr(user, "tipo_usuario", "") or "").upper() == "PROF"

# -------- utilidades geolocalización --------
from math import radians, sin, cos, asin, sqrt

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def _nearest_sede(lat, lng):
    """Devuelve (sede, distancia_m) más cercana con coordenadas válidas, o (None, None)."""
    qs = Sede.objects.exclude(latitud__isnull=True).exclude(longitud__isnull=True)
    best, best_d = None, None
    for s in qs:
        d = _haversine_m(lat, lng, s.latitud, s.longitud)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


# ===================== 1) Marcar mi asistencia (QR / Geo) =====================
@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    # últimas marcas para mostrar en pantalla
    ultima_entrada = (
        AsistenciaProfesor.objects
        .filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.ENTRADA)
        .order_by("-fecha", "-hora").first()
    )
    ultima_salida = (
        AsistenciaProfesor.objects
        .filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.SALIDA)
        .order_by("-fecha", "-hora").first()
    )

    mensaje, ok = None, False

    if request.method == "POST":
        action  = (request.POST.get("action") or "").strip()       # 'entrada'|'salida'
        qr_text = (request.POST.get("qr_text") or "").strip()
        lat_str = request.POST.get("geo_lat")
        lng_str = request.POST.get("geo_lng")

        # 1) Intento por QR
        sede = None
        if qr_text.startswith("SEDE:"):
            try:
                sede_id = int(qr_text.split(":", 1)[1])
                sede = Sede.objects.filter(pk=sede_id).first()
            except ValueError:
                sede = None

        # 2) Si QR no vino o es inválido, intento por geolocalización
        if not sede and lat_str and lng_str:
            try:
                lat, lng = float(lat_str), float(lng_str)
                sede_cerca, d_m = _nearest_sede(lat, lng)
                if sede_cerca and d_m <= (sede_cerca.radio_metros or 150):
                    sede = sede_cerca
                else:
                    mensaje = "No estás dentro del radio de una sede registrada."
            except Exception:
                mensaje = "Ubicación inválida."

        if not sede:
            mensaje = mensaje or "QR inválido o ubicación no válida."
        else:
            hoy   = timezone.localdate()
            ahora = timezone.localtime().time()
            tipo  = (AsistenciaProfesor.Tipo.ENTRADA
                     if action == "entrada"
                     else AsistenciaProfesor.Tipo.SALIDA)

            # evita duplicados del mismo día
            ya_existe = AsistenciaProfesor.objects.filter(
                usuario=request.user, fecha=hoy, tipo=tipo
            ).exists()

            if ya_existe:
                mensaje = (
                    "Ya registraste tu entrada hoy."
                    if tipo == AsistenciaProfesor.Tipo.ENTRADA
                    else "Ya registraste tu salida hoy."
                )
            else:
                AsistenciaProfesor.objects.create(
                    usuario=request.user,
                    sede=sede,
                    fecha=hoy,
                    hora=ahora,
                    tipo=tipo,
                )
                ok = True
                hhmm = timezone.localtime().strftime("%H:%M")
                pref = "Entrada" if tipo == AsistenciaProfesor.Tipo.ENTRADA else "Salida"
                mensaje = f"{pref} registrada correctamente — {hhmm} en {sede.nombre}"

                # refresca “últimas”
                if tipo == AsistenciaProfesor.Tipo.ENTRADA:
                    ultima_entrada = AsistenciaProfesor.objects.filter(
                        usuario=request.user, tipo=AsistenciaProfesor.Tipo.ENTRADA
                    ).order_by("-fecha", "-hora").first()
                else:
                    ultima_salida = AsistenciaProfesor.objects.filter(
                        usuario=request.user, tipo=AsistenciaProfesor.Tipo.SALIDA
                    ).order_by("-fecha", "-hora").first()

    return render(request, "profesor/mi_asistencia_qr.html", {
        "ultima_entrada": ultima_entrada,
        "ultima_salida":  ultima_salida,
        "mensaje":        mensaje,
        "ok":             ok,
    })

@login_required
def mi_historial_asistencia(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    qs = (AsistenciaProfesor.objects
          .select_related("sede")
          .filter(usuario=request.user)
          .order_by("-fecha", "-hora"))

    # filtros opcionales
    f_ini = request.GET.get("ini")
    f_fin = request.GET.get("fin")
    sede  = request.GET.get("sede")
    if f_ini: qs = qs.filter(fecha__gte=f_ini)
    if f_fin: qs = qs.filter(fecha__lte=f_fin)
    if sede:  qs = qs.filter(sede_id=sede)

    # horas trabajadas por día (si hay ENT y SAL)
    by_day = defaultdict(list)
    for a in qs:
        by_day[a.fecha].append(a)

    horas_dia = {}
    for d, items in by_day.items():
        ent = next((i for i in items if i.tipo == "ENT"), None)
        sal = next((i for i in items if i.tipo == "SAL"), None)
        if ent and sal:
            t1 = datetime.combine(d, ent.hora)
            t2 = datetime.combine(d, sal.hora)
            delta = t2 - t1
            if delta.total_seconds() > 0:
                horas_dia[d] = delta

    sedes = Sede.objects.all().order_by("nombre")

    return render(request, "profesor/mi_historial_asistencia.html", {
        "items": qs,
        "sedes": sedes,
        "horas_dia": horas_dia,
        "f_ini": f_ini or "",
        "f_fin": f_fin or "",
        "sede_sel": int(sede) if sede else None,
    })

@login_required
def sedes_qr_list(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    sedes = Sede.objects.all().order_by("nombre")
    return render(request, "profesor/sedes_qr_list.html", {"sedes": sedes})


@login_required
def qr_sede_png(request, sede_id: int):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    sede = get_object_or_404(Sede, pk=sede_id)
    size = int(request.GET.get("s", 12))  # escala

    payload = f"SEDE:{sede.id}"
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                       box_size=max(6, min(size, 30)), border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = HttpResponse(buf.getvalue(), content_type="image/png")
    resp["Content-Disposition"] = f'inline; filename="qr_sede_{sede.id}.png"'
    return resp

@login_required
def placard_sede_qr(request, sede_id: int):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    sede = get_object_or_404(Sede, pk=sede_id)
    return render(request, "profesor/placard_sede_qr.html", {"sede": sede})

@login_required
def alumno_temporal_new(request):
    # solo profesores pueden usar esta vista
    if not hasattr(request.user, "tipo_usuario") or str(request.user.tipo_usuario).upper() != "PROF":
        raise PermissionDenied("Solo disponible para profesores/entrenadores.")

    if request.method == "POST":
        form = AlumnoTemporalForm(request.POST)
        if form.is_valid():
            est = form.save(commit=False)
            est.temporal = True
            est.activo = True
            # Si agregaste el campo creado_por en el modelo:
            # est.creado_por = request.user
            est.save()
            messages.success(request, "Alumno temporal creado correctamente.")
            return redirect("usuarios:panel_profesor")
        else:
            messages.error(request, "Revisa los campos del formulario.")
    else:
        form = AlumnoTemporalForm()

    return render(request, "profesor/alumno_temporal_form.html", {"form": form})