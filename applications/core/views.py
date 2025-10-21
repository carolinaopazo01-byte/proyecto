# applications/core/views.py
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count

from .models import Comunicado, Curso, Sede, Estudiante, Planificacion, Deporte, PlanificacionVersion
#from .forms import PlanificacionForm, DeporteForm, PlanificacionUploadForm
from .forms import DeporteForm, PlanificacionUploadForm
# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario
from applications.atleta.models import Clase, AsistenciaAtleta
from applications.core.models import Sede, Deporte

from datetime import date, timedelta
from django.utils import timezone


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ------- Home (informativo) -------
@require_http_methods(["GET"])
def home(request):
    return render(request, "core/home.html")


# ESTUDIANTES
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def estudiantes_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Estudiante.objects.all().order_by("apellidos", "nombres")
    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(email__icontains=q)
        )
    return render(request, "core/estudiantes_list.html", {"estudiantes": qs, "q": q})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_create(request):
    # import perezoso para evitar problemas durante makemigrations
    from .forms import EstudianteForm
    if request.method == "POST":
        form = EstudianteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm()
    return render(request, "core/estudiante_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def estudiante_edit(request, estudiante_id: int):
    from .forms import EstudianteForm
    obj = get_object_or_404(Estudiante, pk=estudiante_id)
    if request.method == "POST":
        form = EstudianteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:estudiantes_list")
    else:
        form = EstudianteForm(instance=obj)
    return render(request, "core/estudiante_form.html", {"form": form, "is_edit": True, "estudiante": obj})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def estudiante_delete(request, estudiante_id: int):
    Estudiante.objects.filter(pk=estudiante_id).delete()
    return redirect("core:estudiantes_list")


# ================= CURSOS =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def cursos_list(request):
    cursos = Curso.objects.select_related("sede", "profesor").all()
    return render(request, "core/cursos_list.html", {"cursos": cursos})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_create(request):
    from .forms import CursoForm, CursoHorarioFormSet
    if request.method == "POST":
        form = CursoForm(request.POST)
        formset = CursoHorarioFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            curso = form.save()
            formset.instance = curso
            formset.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm()
        formset = CursoHorarioFormSet()
    return render(request, "core/curso_form.html", {
        "form": form, "formset": formset, "is_edit": False
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_edit(request, curso_id: int):
    from .forms import CursoForm, CursoHorarioFormSet
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method == "POST":
        form = CursoForm(request.POST, instance=curso)
        formset = CursoHorarioFormSet(request.POST, instance=curso)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect("core:cursos_list")
    else:
        form = CursoForm(instance=curso)
        formset = CursoHorarioFormSet(instance=curso)
    return render(request, "core/curso_form.html", {
        "form": form, "formset": formset, "is_edit": True, "curso": curso
    })


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def curso_delete(request, curso_id: int):
    Curso.objects.filter(pk=curso_id).delete()
    return redirect("core:cursos_list")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def curso_configurar_cupos(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (POST) -> OK")
    return HttpResponse(f"CORE / Cursos - CONFIGURAR CUPOS curso_id={curso_id} (GET) -> formulario")

# ================= SEDES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def sedes_list(request):
    q = (request.GET.get("q") or "").strip()               # nombre o comuna
    comuna = (request.GET.get("comuna") or "").strip()
    estado = (request.GET.get("estado") or "").strip()     # act | inact | ""
    cap_cmp = (request.GET.get("cap_cmp") or "").strip()   # gt | lt | ""
    try:
        cap_val = int(request.GET.get("cap_val") or 0)
    except ValueError:
        cap_val = 0

    qs = Sede.objects.all().order_by("nombre")

    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(comuna__icontains=q))
    if comuna:
        qs = qs.filter(comuna__iexact=comuna)
    if estado == "act":
        qs = qs.filter(activa=True)
    elif estado == "inact":
        qs = qs.filter(activa=False)
    if cap_cmp == "gt" and cap_val:
        qs = qs.filter(capacidad__gte=cap_val)
    elif cap_cmp == "lt" and cap_val:
        qs = qs.filter(capacidad__lte=cap_val)

    comunas = Sede.objects.exclude(comuna="").values_list("comuna", flat=True).distinct().order_by("comuna")
    return render(request, "core/sedes_list.html", {
        "sedes": qs,
        "q": q,
        "comuna_sel": comuna,
        "estado_sel": estado,
        "cap_cmp": cap_cmp,
        "cap_val": cap_val or "",
        "comunas": comunas,
    })

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def sede_detail(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)
    return render(request, "core/sede_detail.html", {"sede": sede})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def sede_create(request):
    from .forms import SedeForm
    if request.method == "POST":
        form = SedeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:sedes_list")
    else:
        form = SedeForm(initial={"comuna": "Coquimbo"})  # ← prefill
    return render(request, "core/sede_form.html", {"form": form, "is_edit": False})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def sede_edit(request, sede_id: int):
    from .forms import SedeForm
    sede = get_object_or_404(Sede, pk=sede_id)
    if request.method == "POST":
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            form.save()
            return redirect("core:sedes_list")
    else:
        form = SedeForm(instance=sede)
    return render(request, "core/sede_form.html", {"form": form, "is_edit": True, "sede": sede})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def sede_delete(request, sede_id: int):
    sede = get_object_or_404(Sede, pk=sede_id)
    sede.delete()
    return redirect("core:sedes_list")


# ================= COMUNICADOS =================
@role_required(
    Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF,
    Usuario.Tipo.APOD, Usuario.Tipo.ATLE, Usuario.Tipo.PMUL
)
@require_http_methods(["GET"])
def comunicados_list(request):
    data = Comunicado.objects.all().order_by("-creado")[:50]
    return render(request, "core/comunicados_list.html", {"data": data})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
@require_http_methods(["GET", "POST"])
def comunicado_create(request):
    if request.method == "POST":
        titulo = (request.POST.get("titulo") or "").strip()
        cuerpo = (request.POST.get("cuerpo") or "").strip()
        if titulo and cuerpo:
            Comunicado.objects.create(titulo=titulo, cuerpo=cuerpo, autor=request.user)
            return redirect("core:comunicados_list")
        return render(request, "core/comunicado_create.html", {"error": "Completa título y cuerpo."})
    return render(request, "core/comunicado_create.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
@require_http_methods(["GET", "POST"])
def comunicado_edit(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if request.user != com.autor and request.user.tipo_usuario not in [Usuario.Tipo.ADMIN, Usuario.Tipo.COORD]:
        return HttpResponse("No tienes permisos para editar este comunicado.", status=403)
    if request.method == "POST":
        titulo = (request.POST.get("titulo") or "").strip()
        cuerpo = (request.POST.get("cuerpo") or "").strip()
        if titulo and cuerpo:
            com.titulo, com.cuerpo = titulo, cuerpo
            com.save()
            return redirect("core:comunicados_list")
        return render(request, "core/comunicado_edit.html", {"comunicado": com, "error": "Completa título y cuerpo."})
    return render(request, "core/comunicado_edit.html", {"comunicado": com})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF, Usuario.Tipo.PMUL)
@require_http_methods(["POST"])
def comunicado_delete(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if request.user != com.autor and request.user.tipo_usuario not in [Usuario.Tipo.ADMIN, Usuario.Tipo.COORD]:
        return HttpResponse("No tienes permisos para eliminar este comunicado.", status=403)
    com.delete()
    return redirect("core:comunicados_list")


# ================ Páginas informativas ================
@require_http_methods(["GET"])
def quienes_somos(request):
    return render(request, "pages/quienes.html")


@require_http_methods(["GET"])
def procesos_inscripcion(request):
    return render(request, "pages/procesos.html")


@require_http_methods(["GET"])
def deportes_recintos(request):
    return render(request, "pages/deportes.html")


@require_http_methods(["GET"])
def equipo_multidisciplinario(request):
    return render(request, "pages/equipo.html")


# ------- Profesores (stubs mínimos para que no falle urls) -------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def profesores_list(request):
    return render(request, "core/profesores_list.html")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def profesor_create(request):
    if request.method == "POST":
        return HttpResponse("CORE / Profesores - CREAR (POST) -> guardado OK")
    return render(request, "core/profesor_form.html")


# -------- STUBS QUE PUEDEN FALTAR EN URLs --------
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    if request.method == "POST":
        return HttpResponse("CORE / Planificación - SUBIR (POST) -> OK")
    return HttpResponse("CORE / Planificación - SUBIR (GET) -> formulario simple")


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (GET) -> pantalla tomar asistencia")


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def asistencia_estudiantes(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (GET) -> lista alumnos")


@role_required(Usuario.Tipo.PROF, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")


# ================= REPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_home(request):
    return render(request, "core/reportes_home.html")


# --------- 📆 Semanal de inasistencias ----------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def reporte_inasistencias(request):
    # Semana (lunes-domingo) por fecha dada o hoy
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = base - timedelta(days=base.weekday())
    domingo = lunes + timedelta(days=6)

    umbral = int(request.GET.get("umbral") or 2)

    sede_id = request.GET.get("sede") or ""
    deporte_id = request.GET.get("disciplina") or ""
    prof_id = request.GET.get("prof") or ""
    programa = request.GET.get("programa") or ""  # FORM | ALTO | ""

    # Clases en el rango de la semana
    clases = Clase.objects.select_related(
        "profesor", "sede_deporte__sede", "sede_deporte__deporte"
    ).filter(fecha__range=(lunes, domingo))

    # Filtros opcionales
    if sede_id:
        clases = clases.filter(sede_deporte__sede_id=sede_id)
    if deporte_id:
        clases = clases.filter(sede_deporte__deporte_id=deporte_id)
    if prof_id:
        clases = clases.filter(profesor_id=prof_id)
    # Si quieres filtrar por programa y tienes ese campo en Curso (no en Clase),
    # déjalo sin efecto por ahora o mapea tu modelo aquí.

    # KPI
    asist = AsistenciaAtleta.objects.filter(clase__in=clases).select_related("atleta")
    total_presentes = asist.filter(presente=True).count()
    total_ausentes = asist.filter(presente=False).count()
    total_registros = total_presentes + total_ausentes
    alumnos_con_falta = asist.filter(presente=False).values_list("atleta_id", flat=True).distinct().count()

    # Alumnos con alerta (>= umbral faltas en la semana)
    from django.db.models import Count, Q
    alerta_ids = (
        asist.values("atleta_id")
        .annotate(faltas=Count("id", filter=Q(presente=False)))
        .filter(faltas__gte=umbral)
        .values_list("atleta_id", flat=True)
    )
    alumnos_alerta = len(list(alerta_ids))
    pct_asistencia = round((total_presentes / total_registros) * 100, 1) if total_registros else 0.0

    # Tabla principal agrupada por clase (curso no está en Clase; usamos clase como fila)
    filas = []
    for c in clases.order_by("fecha", "hora_inicio"):
        qs = asist.filter(clase=c)
        presentes = qs.filter(presente=True).count()
        ausentes = qs.filter(presente=False).count()
        inscritos = presentes + ausentes
        pct = round((presentes / inscritos) * 100, 1) if inscritos else 0.0
        filas.append({
            "clase": c,
            "curso": getattr(c, "tema", "") or getattr(c.sede_deporte, "deporte", ""),  # etiqueta amigable
            "profesor": c.profesor.get_full_name() if c.profesor else "—",
            "sede": getattr(c.sede_deporte, "sede", None),
            "dia": c.fecha.strftime("%a"),
            "fecha": c.fecha,
            "inscritos": inscritos,
            "presentes": presentes,
            "ausentes": ausentes,
            "pct": pct,
        })

    ctx = {
        "lunes": lunes, "domingo": domingo,
        "semana": base.isoformat(),
        "umbral": umbral,
        "kpi_total_ausentes": total_ausentes,
        "kpi_alumnos_con_falta": alumnos_con_falta,
        "kpi_alertas": alumnos_alerta,
        "kpi_pct": pct_asistencia,
        "filas": filas,
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "profes": Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).order_by("last_name", "first_name"),
        "programa": programa,
    }
    return render(request, "core/reporte_inasistencias.html", ctx)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_inasistencias_export_csv(request):
    # mismo rango/filters que reporte_inasistencias
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = base - timedelta(days=base.weekday())
    domingo = lunes + timedelta(days=6)

    clases = Clase.objects.select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte") \
        .filter(fecha__range=(lunes, domingo))
    sede_id = request.GET.get("sede") or ""
    deporte_id = request.GET.get("disciplina") or ""
    prof_id = request.GET.get("prof") or ""
    if sede_id: clases = clases.filter(sede_deporte__sede_id=sede_id)
    if deporte_id: clases = clases.filter(sede_deporte__deporte_id=deporte_id)
    if prof_id: clases = clases.filter(profesor_id=prof_id)

    asist = AsistenciaAtleta.objects.filter(clase__in=clases)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="reporte_inasistencias.csv"'
    resp.write("\ufeff")
    resp.write("Curso,Profesor,Sede,Fecha,Inscritos,Presentes,Ausentes,%Asistencia\n")
    for c in clases.order_by("fecha", "hora_inicio"):
        qs = asist.filter(clase=c)
        p = qs.filter(presente=True).count()
        a = qs.filter(presente=False).count()
        tot = p + a
        pct = round((p / tot) * 100, 1) if tot else 0
        etiqueta = getattr(c, "tema", "") or str(getattr(c.sede_deporte, "deporte", ""))
        resp.write(f'"{etiqueta}","{c.profesor or ""}","{getattr(c.sede_deporte, "sede", "")}",{c.fecha},{tot},{p},{a},{pct}\n')
    return resp


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_inasistencias_detalle(request, clase_id: int):
    clase = get_object_or_404(Clase.objects.select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte"), pk=clase_id)
    semana_base = clase.fecha
    lunes = semana_base - timedelta(days=semana_base.weekday())
    domingo = lunes + timedelta(days=6)

    # Faltas de la semana por atleta
    asist_semana = AsistenciaAtleta.objects.filter(
        atleta__isnull=False,
        clase__fecha__range=(lunes, domingo)
    ).select_related("atleta__usuario")

    registros_clase = AsistenciaAtleta.objects.filter(clase=clase).select_related("atleta__usuario")
    filas = []
    from django.db.models import Count, Q
    faltas_semana = asist_semana.values("atleta_id").annotate(faltas=Count("id", filter=Q(presente=False)))
    faltas_map = {r["atleta_id"]: r["faltas"] for r in faltas_semana}

    for r in registros_clase:
        at = r.atleta
        nombre = at.usuario.get_full_name() if at and at.usuario_id else "—"
        rut = getattr(at, "rut", "—")
        tel_apod = getattr(getattr(at, "apoderado", None), "telefono", "") or ""  # si existe
        # últimas 4 asistencias del atleta (global)
        ult4 = AsistenciaAtleta.objects.filter(atleta=at).order_by("-clase__fecha")[:4]
        faltas_ult4 = sum(1 for x in ult4 if not x.presente)
        filas.append({
            "rut": rut,
            "nombre": nombre,
            "faltas_semana": faltas_map.get(at.id, 0),
            "faltas_ult4": faltas_ult4,
            "tel_apod": tel_apod,
            "presente": r.presente,
            "observ": r.observaciones,
        })

    return render(request, "core/reporte_inasistencias_detalle.html", {
        "clase": clase,
        "lunes": lunes, "domingo": domingo,
        "filas": filas,
    })


# --------- 🧑‍🏫 Asistencia por clase (selector) ----------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request):
    # Filtros: Curso (si lo usas), Sede/Disciplina, Fecha
    fecha = request.GET.get("fecha") or ""
    try:
        fecha_dt = date.fromisoformat(fecha) if fecha else None
    except ValueError:
        fecha_dt = None

    sede_id = request.GET.get("sede") or ""
    deporte_id = request.GET.get("disciplina") or ""
    clase_id = request.GET.get("clase") or ""

    clases = Clase.objects.select_related("profesor", "sede_deporte__sede", "sede_deporte__deporte").all()
    if fecha_dt:
        clases = clases.filter(fecha=fecha_dt)
    if sede_id:
        clases = clases.filter(sede_deporte__sede_id=sede_id)
    if deporte_id:
        clases = clases.filter(sede_deporte__deporte_id=deporte_id)

    seleccionada = None
    registros = []
    if clase_id:
        seleccionada = get_object_or_404(clases, pk=clase_id)
        registros = AsistenciaAtleta.objects.filter(clase=seleccionada).select_related("atleta__usuario").order_by("atleta__usuario__last_name")

    return render(request, "core/reporte_asistencia_clase.html", {
        "fecha": fecha,
        "sede_id": sede_id,
        "deporte_id": deporte_id,
        "clase_id": int(clase_id) if clase_id else "",
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "clases": clases.order_by("-fecha", "hora_inicio"),
        "seleccionada": seleccionada,
        "registros": registros,
    })


# -------- Placeholders: en blanco por ahora --------
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_curso(request):  # TODO
    return render(request, "core/reporte_placeholder.html", {"titulo": "Asistencia por curso (rango) – próximamente"})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_sede(request):  # TODO
    return render(request, "core/reporte_placeholder.html", {"titulo": "Asistencia por sede (rango) – próximamente"})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_llegadas_tarde(request):  # TODO
    return render(request, "core/reporte_placeholder.html", {"titulo": "Llegadas tarde – próximamente"})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_exportar_todo(request):  # TODO
    return HttpResponse("Exportador general (xlsx/pdf) – por implementar")

# ================= PLANIFICACIONES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificaciones_list(request):
    """
    Panel con filtros + KPIs + tabla.
    """
    # Filtros
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = _monday(base)

    programa = (request.GET.get("programa") or "").strip()  # FORM | ALTO | ""
    sede_id = request.GET.get("sede") or ""
    dep_id = request.GET.get("disciplina") or ""
    curso_id = request.GET.get("curso") or ""
    prof_id = request.GET.get("prof") or ""

    # Cursos base (para KPI de total cursos)
    cursos_qs = Curso.objects.select_related("sede", "profesor", "disciplina").all()
    if programa:
        cursos_qs = cursos_qs.filter(programa=programa)
    if sede_id:
        cursos_qs = cursos_qs.filter(sede_id=sede_id)
    if dep_id:
        cursos_qs = cursos_qs.filter(disciplina_id=dep_id)
    if curso_id:
        cursos_qs = cursos_qs.filter(id=curso_id)
    if prof_id:
        cursos_qs = cursos_qs.filter(profesor_id=prof_id)

    total_cursos = cursos_qs.count()

    # Planificaciones de esa semana y filtros
    plans = (Planificacion.objects
             .select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina")
             .filter(semana=lunes))

    if programa:
        plans = plans.filter(curso__programa=programa)
    if sede_id:
        plans = plans.filter(curso__sede_id=sede_id)
    if dep_id:
        plans = plans.filter(curso__disciplina_id=dep_id)
    if curso_id:
        plans = plans.filter(curso_id=curso_id)
    if prof_id:
        plans = plans.filter(curso__profesor_id=prof_id)

    cursos_con_plan = plans.values("curso_id").distinct().count()
    pct_subidas = round((cursos_con_plan / total_cursos) * 100, 1) if total_cursos else 0.0

    ctx = {
        "semana": base.isoformat(),
        "lunes": lunes,
        "total_cursos": total_cursos,
        "pct_subidas": pct_subidas,
        "items": plans.order_by("curso__sede__nombre", "curso__disciplina__nombre", "curso__nombre"),
        "sedes": Sede.objects.order_by("nombre"),
        "disciplinas": Deporte.objects.order_by("nombre"),
        "cursos": cursos_qs.order_by("nombre"),
        "profes": Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).order_by("last_name", "first_name"),
        "programa": programa,
        "sede_id": sede_id,
        "dep_id": dep_id,
        "curso_id": curso_id,
        "prof_id": prof_id,
    }
    return render(request, "core/planificaciones_list.html", ctx)

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def planificacion_upload(request):
    """
    Sube/actualiza la planificación de un curso en una semana.
    Si ya existe, actualiza archivo y guarda versión en historial.
    """
    if request.method == "POST":
        form = PlanificacionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            # normalizar: guardar el LUNES de esa semana
            obj.semana = _monday(obj.semana)
            obj.autor = request.user
            # ¿ya existe?
            existente = Planificacion.objects.filter(curso=obj.curso, semana=obj.semana).first()
            if existente:
                # guardar versión actual si tenía archivo
                if existente.archivo:
                    PlanificacionVersion.objects.create(
                        planificacion=existente,
                        archivo=existente.archivo,
                        autor=request.user,
                    )
                existente.archivo = obj.archivo
                existente.autor = request.user
                existente.save()
                return redirect("core:planificaciones_list")
            else:
                obj.save()
                return redirect("core:planificaciones_list")
    else:
        # semana por defecto: hoy
        form = PlanificacionUploadForm(initial={"semana": timezone.localdate()})
    return render(request, "core/planificacion_form_upload.html", {"form": form})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_detail(request, plan_id: int):
    p = get_object_or_404(
        Planificacion.objects.select_related("curso", "curso__sede", "curso__profesor", "curso__disciplina"),
        pk=plan_id
    )
    return render(request, "core/planificacion_detail.html", {"p": p})

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_download(request, plan_id: int):
    p = get_object_or_404(Planificacion, pk=plan_id)
    if not p.archivo:
        raise Http404("No hay archivo para descargar.")
    return FileResponse(p.archivo.open("rb"), as_attachment=True, filename=p.archivo.name.split("/")[-1])

@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificacion_historial(request, plan_id: int):
    p = get_object_or_404(Planificacion, pk=plan_id)
    versiones = p.versiones.all()
    return render(request, "core/planificacion_historial.html", {"p": p, "versiones": versiones})
# ================= DEPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def deportes_list(request):
    items = Deporte.objects.all().order_by("nombre")
    return render(request, "core/deportes_list.html", {"items": items})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def deporte_create(request):
    if request.method == "POST":
        form = DeporteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:deportes_list")
    else:
        form = DeporteForm()
    return render(request, "core/deporte_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def deporte_edit(request, deporte_id: int):
    obj = get_object_or_404(Deporte, pk=deporte_id)
    if request.method == "POST":
        form = DeporteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:deportes_list")
    else:
        form = DeporteForm(instance=obj)
    return render(request, "core/deporte_form.html", {"form": form, "is_edit": True, "obj": obj})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def deporte_delete(request, deporte_id: int):
    get_object_or_404(Deporte, pk=deporte_id).delete()
    return redirect("core:deportes_list")
