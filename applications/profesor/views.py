from datetime import datetime
from collections import defaultdict
from math import radians, sin, cos, asin, sqrt
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from applications.core.models import (
    Sede,
    Curso,
    Estudiante,
    AsistenciaCurso,
    AsistenciaCursoDetalle,
)
from .models import AsistenciaProfesor


# ===================== UTILIDADES =====================
def _es_prof(user) -> bool:
    """Retorna True si el usuario es de tipo PROF."""
    return (getattr(user, "tipo_usuario", "") or "").upper() == "PROF"


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distancia en metros entre dos coordenadas."""
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def _nearest_sede(lat, lng):
    """Devuelve la sede más cercana dentro del radio permitido."""
    qs = Sede.objects.exclude(latitud__isnull=True).exclude(longitud__isnull=True)
    best, best_d = None, None
    for s in qs:
        d = _haversine_m(lat, lng, s.latitud, s.longitud)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


# ===================== 1) Marcar asistencia (QR / Geo) =====================
@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    ultima_entrada = (
        AsistenciaProfesor.objects.filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.ENTRADA)
        .order_by("-fecha", "-hora")
        .first()
    )
    ultima_salida = (
        AsistenciaProfesor.objects.filter(usuario=request.user, tipo=AsistenciaProfesor.Tipo.SALIDA)
        .order_by("-fecha", "-hora")
        .first()
    )

    mensaje, ok = None, False

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        qr_text = (request.POST.get("qr_text") or "").strip()
        lat_str = request.POST.get("geo_lat")
        lng_str = request.POST.get("geo_lng")

        # Intento con QR
        sede = None
        if qr_text.startswith("SEDE:"):
            try:
                sede_id = int(qr_text.split(":", 1)[1])
                sede = Sede.objects.filter(pk=sede_id).first()
            except ValueError:
                sede = None

        # Intento con geolocalización
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
            hoy = timezone.localdate()
            ahora = timezone.localtime().time()
            tipo = (
                AsistenciaProfesor.Tipo.ENTRADA
                if action == "entrada"
                else AsistenciaProfesor.Tipo.SALIDA
            )

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
        "ultima_salida": ultima_salida,
        "mensaje": mensaje,
        "ok": ok,
    })


# ===================== 2) Historial de asistencia =====================
@login_required
def mi_historial_asistencia(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    qs = (
        AsistenciaProfesor.objects.select_related("sede")
        .filter(usuario=request.user)
        .order_by("-fecha", "-hora")
    )

    # filtros opcionales
    f_ini = request.GET.get("ini")
    f_fin = request.GET.get("fin")
    sede = request.GET.get("sede")

    if f_ini:
        qs = qs.filter(fecha__gte=f_ini)
    if f_fin:
        qs = qs.filter(fecha__lte=f_fin)
    if sede:
        qs = qs.filter(sede_id=sede)

    # cálculo de horas por día
    by_day = defaultdict(list)
    for a in qs:
        by_day[a.fecha].append(a)

    horas_dia = {}
    for d, items in by_day.items():
        ent = next((i for i in items if i.tipo == AsistenciaProfesor.Tipo.ENTRADA), None)
        sal = next((i for i in items if i.tipo == AsistenciaProfesor.Tipo.SALIDA), None)
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


# ===================== 3) Sedes y QR =====================
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
    size = int(request.GET.get("s", 12))

    payload = f"SEDE:{sede.id}"
    qr = qrcode.QRCode(
        version=None,
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
    resp["Content-Disposition"] = f'inline; filename="qr_sede_{sede.id}.png"'
    return resp


@login_required
def placard_sede_qr(request, sede_id: int):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    sede = get_object_or_404(Sede, pk=sede_id)
    return render(request, "profesor/placard_sede_qr.html", {"sede": sede})


# ===================== 4) Mis cursos =====================
@login_required
def mis_cursos_prof(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    cursos = Curso.objects.filter(profesor=request.user).order_by("-creado")
    return render(request, "profesor/mis_cursos_prof.html", {"cursos": cursos})


# ===================== 5) Toma de asistencia con alumnos =====================


@login_required
def asistencia_tomar(request, curso_id):
    """Toma asistencia mostrando alumnos y guardando estados + observaciones."""
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    profesor = request.user
    curso = get_object_or_404(Curso, pk=curso_id)

    # crear o recuperar asistencia del día
    hoy = timezone.localdate()
    asistencia, _ = AsistenciaCurso.objects.get_or_create(
        curso=curso,
        fecha=hoy,
        defaults={"creado_por": profesor, "estado": AsistenciaCurso.Estado.PEND},
    )

    # alumnos activos del curso
    alumnos = Estudiante.objects.filter(curso=curso, activo=True).order_by("apellidos", "nombres")

    # ============ GUARDAR CAMBIOS ============
    if request.method == "POST":
        accion = request.POST.get("accion", "").strip().lower()

        # Guardar estados y observaciones
        if accion == "guardar":
            for est in alumnos:
                # busca el detalle o lo crea
                detalle, _ = AsistenciaCursoDetalle.objects.get_or_create(
                    asistencia=asistencia,
                    estudiante=est,
                )
                estado = request.POST.get(f"estado_{detalle.id}", detalle.estado)
                obs = request.POST.get(f"obs_{detalle.id}", detalle.observaciones)
                detalle.estado = estado or "P"
                detalle.observaciones = obs or ""
                detalle.save()
            messages.success(request, "✅ Asistencia de alumnos guardada correctamente.")
            return redirect("profesor:asistencia_tomar", curso_id=curso.id)

        # Marcar entrada / salida del profesor
        if accion == "entrada":
            asistencia.estado = AsistenciaCurso.Estado.ENCU
            asistencia.inicio_real = timezone.localtime().time()
            asistencia.save()
            messages.info(request, "Entrada registrada correctamente.")
            return redirect("profesor:asistencia_tomar", curso_id=curso.id)

        if accion == "salida":
            asistencia.estado = AsistenciaCurso.Estado.CERR
            asistencia.fin_real = timezone.localtime().time()
            asistencia.save()
            messages.info(request, "Salida registrada correctamente.")
            return redirect("profesor:asistencia_tomar", curso_id=curso.id)

    # ============ CONSTRUCCIÓN DE CONTEXTO PARA EL TEMPLATE ============
    rows = []
    for est in alumnos:
        detalle, _ = AsistenciaCursoDetalle.objects.get_or_create(
            asistencia=asistencia,
            estudiante=est,
            defaults={"estado": "P", "observaciones": ""},
        )
        rows.append({
            "ins": {"id": detalle.id, "estudiante": est},
            "code": detalle.estado,
            "obs": detalle.observaciones,
        })

    resumen = asistencia.resumen if hasattr(asistencia, "resumen") else {"P": 0, "A": 0, "J": 0, "total": len(rows)}

    context = {
        "curso": curso,
        "clase": asistencia,
        "rows": rows,
        "resumen": resumen,
    }
    return render(request, "profesor/asistencia_tomar.html", context)

# ===================== 6) Alumno temporal =====================
@login_required
@require_http_methods(["GET", "POST"])
def alumno_temporal_new(request):
    """Formulario rápido para crear un alumno temporal."""
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    try:
        from applications.core.forms import AlumnoTemporalForm
    except Exception:
        return HttpResponse("No se pudo cargar AlumnoTemporalForm.", status=500)

    if request.method == "POST":
        form = AlumnoTemporalForm(request.POST)
        if form.is_valid():
            est = form.save()
            messages.success(request, f"Alumno temporal creado: {est.nombres} {est.apellidos}.")
            return redirect("core:estudiantes_list_prof")
        messages.error(request, "Revisa los errores del formulario.")
    else:
        form = AlumnoTemporalForm()

    return render(request, "profesor/alumno_temporal_new.html", {"form": form})
