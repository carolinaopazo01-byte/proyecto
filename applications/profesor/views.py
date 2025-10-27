# applications/profesor/views.py
from datetime import datetime, timedelta
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.contrib import messages

from io import BytesIO
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import qrcode
from qrcode.constants import ERROR_CORRECT_M

from applications.core.models import Sede
from .models import AsistenciaProfesor

def _es_prof(user) -> bool:
    return (getattr(user, "tipo_usuario", "") or "").upper() == "PROF"


@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

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

    mensaje = None
    ok = False

    if request.method == "POST":
        action = request.POST.get("action")
        qr_text = request.POST.get("qr_text", "").strip()
        sede_id = None

        if qr_text.startswith("SEDE:"):
            try:
                sede_id = int(qr_text.split(":", 1)[1])
            except ValueError:
                pass

        if not sede_id:
            mensaje = "QR inválido."
        else:
            sede = Sede.objects.filter(pk=sede_id).first()
            if not sede:
                mensaje = "Sede no encontrada."
            else:
                hoy = timezone.localdate()
                ahora = timezone.localtime().time()
                tipo = AsistenciaProfesor.ENTRADA if action == "entrada" else AsistenciaProfesor.SALIDA
                existe = AsistenciaProfesor.objects.filter(
                    usuario=request.user, fecha=hoy, tipo=tipo
                ).exists()

                if existe:
                    mensaje = (
                        "Ya registraste tu entrada hoy."
                        if tipo == "ENT"
                        else "Ya registraste tu salida hoy."
                    )
                else:
                    AsistenciaProfesor.objects.create(
                        usuario=request.user, sede=sede, fecha=hoy, hora=ahora, tipo=tipo
                    )
                    ok = True
                    hhmm = timezone.localtime().strftime("%H:%M")
                    pref = "Entrada" if tipo == "ENT" else "Salida"
                    mensaje = f"{pref} registrada correctamente — {hhmm} en {sede.nombre}"

    return render(request, "profesor/mi_asistencia_qr.html", {
        "ultima_entrada": ultima_entrada,
        "ultima_salida": ultima_salida,
        "mensaje": mensaje,
        "ok": ok,
    })


@login_required
def mi_historial_asistencia(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    qs = AsistenciaProfesor.objects.select_related("sede").filter(usuario=request.user)
    f_ini = request.GET.get("ini")
    f_fin = request.GET.get("fin")
    sede = request.GET.get("sede")

    if f_ini:
        qs = qs.filter(fecha__gte=f_ini)
    if f_fin:
        qs = qs.filter(fecha__lte=f_fin)
    if sede:
        qs = qs.filter(sede_id=sede)

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
    """Listado de sedes con accesos para descargar QR y ver/ imprimir el placard."""
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    sedes = Sede.objects.all().order_by("nombre")
    return render(request, "profesor/sedes_qr_list.html", {"sedes": sedes})


@login_required
def qr_sede_png(request, sede_id: int):
    """Devuelve el PNG del QR de la sede (contenido: SEDE:<id>). Tamaño opcional ?s=10..30."""
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    sede = get_object_or_404(Sede, pk=sede_id)
    size = int(request.GET.get("s", 12))  # box_size (escala). 10-20 suele ir bien.

    payload = f"SEDE:{sede.id}"

    qr = qrcode.QRCode(
        version=None,  # automático
        error_correction=ERROR_CORRECT_M,
        box_size=max(6, min(size, 30)),
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = HttpResponse(buf.getvalue(), content_type="image/png")
    # nombre sugerido de archivo
    resp["Content-Disposition"] = f'inline; filename="qr_sede_{sede.id}.png"'
    return resp


@login_required
def placard_sede_qr(request, sede_id: int):
    """
    Muestra una página de impresión con el QR grande + datos de la sede.
    Ideal para imprimir y pegar en la entrada.
    """
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    sede = get_object_or_404(Sede, pk=sede_id)
    # el <img> del template usará la vista `qr_sede_png`
    return render(request, "profesor/placard_sede_qr.html", {"sede": sede})