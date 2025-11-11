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
from django.db.models import Count, Q
from django.core.paginator import Paginator
from applications.usuarios.models import Usuario
from applications.usuarios.decorators import role_required


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



def _es_prof(user) -> bool:

    return (getattr(user, "tipo_usuario", "") or "").upper() == "PROF"


def _haversine_m(lat1, lon1, lat2, lon2) -> float:

    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def _nearest_sede(lat, lng):

    qs = Sede.objects.exclude(latitud__isnull=True).exclude(longitud__isnull=True)
    best, best_d = None, None
    for s in qs:
        d = _haversine_m(lat, lng, s.latitud, s.longitud)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d

@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):

    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    from django.db.models import Q
    ACC_MAX = 700  # tolerancia máxima por precisión del navegador (m)


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

    # Cursos del profe
    mis_cursos = (
        Curso.objects
        .filter(Q(profesor=request.user) | Q(profesores_apoyo=request.user))
        .select_related("sede")
        .distinct()
        .order_by("nombre")
    )

    # Curso seleccionado o fallback si hay 1
    curso_sel = None
    curso_id = request.GET.get("curso") or request.POST.get("curso")
    if curso_id:
        curso_sel = get_object_or_404(Curso, pk=curso_id)
        if not (
            curso_sel.profesor_id == request.user.id
            or curso_sel.profesores_apoyo.filter(id=request.user.id).exists()
        ):
            return HttpResponseForbidden("No tienes acceso a este curso.")
    elif mis_cursos.count() == 1:
        curso_sel = mis_cursos[0]

    # Radio temporal de prueba
    radio_test = None
    try:
        radio_test = int(request.GET.get("r") or request.POST.get("radio_test") or 0)
        if radio_test <= 0:
            radio_test = None
        else:
            radio_test = max(50, min(2000, radio_test))
    except (TypeError, ValueError):
        radio_test = None

    mensaje, ok = None, False

    if request.method == "POST":
        action  = (request.POST.get("action") or "").strip().lower()  # "entrada" | "salida"
        lat_str = request.POST.get("geo_lat")
        lng_str = request.POST.get("geo_lng")

        # precisión del navegador (m)
        try:
            acc = float(request.POST.get("geo_acc") or 0.0)
        except (TypeError, ValueError):
            acc = 0.0
        acc_clip = max(0.0, min(acc, ACC_MAX))

        sede = None
        if lat_str and lng_str:
            try:
                lat, lng = float(lat_str), float(lng_str)


                if (
                    curso_sel and getattr(curso_sel, "sede", None)
                    and curso_sel.sede.latitud is not None and curso_sel.sede.longitud is not None
                ):
                    d_m = _haversine_m(lat, lng, curso_sel.sede.latitud, curso_sel.sede.longitud)
                    base_curso = (radio_test or curso_sel.sede.radio_metros or 150)
                    radio_eff_curso = base_curso + acc_clip
                    if d_m <= radio_eff_curso:
                        sede = curso_sel.sede
                    else:
                        mensaje = (
                            f"No estás dentro del radio de la sede del curso "
                            f"({int(d_m)} m; radio {base_curso}+{int(acc_clip)}≈{int(radio_eff_curso)} m; "
                            f"precisión {int(acc)} m)."
                        )


                if not sede:
                    sede_cerca, d2 = _nearest_sede(lat, lng)
                    if sede_cerca:
                        base_near = (radio_test or sede_cerca.radio_metros or 150)
                        radio_eff_near = base_near + acc_clip
                        if d2 <= radio_eff_near:
                            sede = sede_cerca
                        else:
                            mensaje = mensaje or (
                                f"No estás dentro del radio de «{sede_cerca.nombre}» "
                                f"(a {int(d2)} m; radio {base_near}+{int(acc_clip)}≈{int(radio_eff_near)} m; "
                                f"precisión {int(acc)} m)."
                            )
                    else:
                        mensaje = mensaje or "No estás dentro del radio de una sede registrada."
            except Exception:
                mensaje = "Ubicación inválida."
        else:
            mensaje = "Activa la ubicación para poder registrar la asistencia."


        if sede:
            hoy = timezone.localdate()
            ahora = timezone.localtime().time()
            tipo = AsistenciaProfesor.Tipo.ENTRADA if action == "entrada" else AsistenciaProfesor.Tipo.SALIDA

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

                # refrescar mostradores
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
        "curso_sel": curso_sel,
        "mis_cursos": mis_cursos,
        "radio_test": radio_test,
    })


# Historial de asistencia
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


@login_required
def mis_cursos_prof(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    cursos = Curso.objects.filter(profesor=request.user).order_by("-creado")
    return render(request, "profesor/mis_cursos_prof.html", {"cursos": cursos})




@login_required
def asistencia_tomar(request, curso_id):

    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    profesor = request.user
    curso = get_object_or_404(Curso, pk=curso_id)

    hoy = timezone.localdate()
    asistencia, _ = AsistenciaCurso.objects.get_or_create(
        curso=curso,
        fecha=hoy,
        defaults={"creado_por": profesor, "estado": AsistenciaCurso.Estado.PEND},
    )

    alumnos = Estudiante.objects.filter(curso=curso, activo=True).order_by("apellidos", "nombres")


    if request.method == "POST":
        accion = request.POST.get("accion", "").strip().lower()

        # Guardar estados y observaciones
        if accion == "guardar":
            for est in alumnos:

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


@login_required
@require_http_methods(["GET", "POST"])
def alumno_temporal_new(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")

    from applications.profesor.forms import AlumnoTemporalForm

    if request.method == "POST":
        form = AlumnoTemporalForm(request.POST)
        if form.is_valid():
            est = form.save(commit=False)
            if hasattr(est, "profesor") and not est.profesor_id:
                est.profesor = request.user
            est.save()


            from applications.core.services import crear_postulacion_desde_temporal
            crear_postulacion_desde_temporal(temporal=est, usuario_creador=request.user)

            messages.success(request, f"✅ Alumno temporal creado y enviado como solicitud: {est.nombres} {est.apellidos}.")
            return redirect("usuarios:panel_profesor")

        messages.error(request, "Revisa los errores del formulario.")
    else:
        form = AlumnoTemporalForm()

    return render(request, "profesor/alumno_temporal_new.html", {"form": form})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def asistencia_historial(request, curso_id: int):

    from django.core.paginator import Paginator
    from django.db.models import Count, Q

    curso = get_object_or_404(Curso, pk=curso_id)

    # Si es PROF, validar que sea titular o apoyo
    es_prof = (getattr(request.user, "tipo_usuario", "").upper() == "PROF")
    if es_prof:
        es_titular = getattr(curso, "profesor_id", None) == request.user.id
        es_apoyo = False
        if hasattr(curso, "profesores_apoyo"):
            try:
                es_apoyo = curso.profesores_apoyo.filter(id=request.user.id).exists()
            except Exception:
                es_apoyo = False
        if not (es_titular or es_apoyo):
            return HttpResponseForbidden("No puedes ver el historial de este curso.")

    # Parámetros de consulta
    est_id = request.GET.get("est")  # opcional: ver historial de un alumno
    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.GET.get("per_page", 20))
    except ValueError:
        per_page = 20

    # Selector de alumnos (solo activos) para el filtro del template
    alumnos_qs = Estudiante.objects.filter(curso=curso, activo=True).order_by("apellidos", "nombres")


    if est_id:
        estudiante = get_object_or_404(Estudiante, pk=est_id, curso=curso)

        det_qs = (
            AsistenciaCursoDetalle.objects
            .select_related("asistencia")
            .filter(asistencia__curso=curso, estudiante=estudiante)
            .order_by("-asistencia__fecha", "-id")
        )

        paginator = Paginator(det_qs, per_page)
        detalles = paginator.get_page(page)

        agg = det_qs.aggregate(
            total=Count("id"),
            P=Count("id", filter=Q(estado="P")),
            A=Count("id", filter=Q(estado="A")),
            J=Count("id", filter=Q(estado="J")),
        )
        resumen = {
            "P": agg["P"] or 0,
            "A": agg["A"] or 0,
            "J": agg["J"] or 0,
            "total": agg["total"] or 0,
        }

        return render(request, "profesor/asistencia_historial.html", {
            "curso": curso,
            "modo": "estudiante",
            "estudiante": estudiante,
            "detalles": detalles,   # Page object
            "resumen": resumen,
            "alumnos": alumnos_qs,
        })

    # ===== Modo CURSO =====
    sesiones_qs = (
        AsistenciaCurso.objects
        .filter(curso=curso)
        .annotate(
            n_total=Count("detalles"),
            n_p=Count("detalles", filter=Q(detalles__estado="P")),
            n_a=Count("detalles", filter=Q(detalles__estado="A")),
            n_j=Count("detalles", filter=Q(detalles__estado="J")),
        )
        .order_by("-fecha", "-id")
    )

    paginator = Paginator(sesiones_qs, per_page)
    sesiones = paginator.get_page(page)

    # KPI global del curso (todas las sesiones)
    g = AsistenciaCursoDetalle.objects.filter(asistencia__curso=curso).aggregate(
        total=Count("id"),
        P=Count("id", filter=Q(estado="P")),
        A=Count("id", filter=Q(estado="A")),
        J=Count("id", filter=Q(estado="J")),
    )
    kpi_global = {
        "P": g["P"] or 0,
        "A": g["A"] or 0,
        "J": g["J"] or 0,
        "total": g["total"] or 0,
    }

    return render(request, "profesor/asistencia_historial.html", {
        "curso": curso,
        "modo": "curso",
        "sesiones": sesiones,     # Page object
        "kpi_global": kpi_global,
        "alumnos": alumnos_qs,
    })