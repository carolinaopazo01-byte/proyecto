# applications/core/views.py
from datetime import timedelta, date
from math import radians, sin, cos, asin, sqrt

from django.http import HttpResponse, FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.core.paginator import Paginator

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import (
    Comunicado, Curso, Sede, Estudiante, Planificacion, Deporte, PlanificacionVersion,
    Noticia,  # ← NUEVO
)
from .forms import DeporteForm, PlanificacionUploadForm, ComunicadoForm, NoticiaForm  # ← NUEVO

from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario
from applications.atleta.models import Clase, AsistenciaAtleta
# from applications.profesor.models import AsistenciaProfesor  # si aplica


# -------- Helpers --------
def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _es_prof(user) -> bool:
    return getattr(user, "tipo_usuario", None) == Usuario.Tipo.PROF


def _is_admin_or_coord(user) -> bool:
    return getattr(user, "tipo_usuario", None) in (Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)


# ------- Home (informativo) -------
@require_http_methods(["GET"])
def home(request):
    # Slides: últimas noticias publicadas con IMAGEN (máx. 6)
    noticias_slider = (
        Noticia.objects.filter(publicada=True)
        .exclude(imagen="").exclude(imagen__isnull=True)
        .order_by("-publicada_en", "-creado")[:6]
    )

    # Tarjetas/últimas noticias (puedes usarlas en una sección más abajo)
    noticias = (
        Noticia.objects.filter(publicada=True)
        .order_by("-publicada_en", "-creado")[:6]
    )

    return render(
        request,
        "core/home.html",
        {
            "noticias_slider": noticias_slider,
            "noticias": noticias,
        },
    )


# ================= ESTUDIANTES =================
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
    cursos = (
        Curso.objects
        .select_related("sede", "profesor", "disciplina")
        .prefetch_related("horarios")
        .all()
    )
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
    q = (request.GET.get("q") or "").strip()
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
        form = SedeForm(initial={"comuna": "Coquimbo"})  # fix initial como dict
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
    """
    Lista de comunicados visibles para el usuario actual.
    Depende del manager `for_user` del modelo Comunicado (audiencia por códigos y/o grupos).
    """
    comunicados = None
    try:
        if hasattr(Comunicado.objects, "for_user"):
            comunicados = Comunicado.objects.for_user(request.user).order_by("-creado", "-id")[:50]
    except Exception:
        comunicados = None

    if comunicados is None:
        # Fallback si no existiera el manager
        if hasattr(Comunicado, "creado"):
            comunicados = Comunicado.objects.all().order_by("-creado", "-id")[:50]
        elif hasattr(Comunicado, "fecha"):
            comunicados = Comunicado.objects.all().order_by("-fecha", "-id")[:50]
        elif hasattr(Comunicado, "created_at"):
            comunicados = Comunicado.objects.all().order_by("-created_at", "-id")[:50]
        else:
            comunicados = Comunicado.objects.all().order_by("-id")[:50]

    return render(request, "core/comunicados_list.html", {
        "comunicados": comunicados,
        "puede_crear": _is_admin_or_coord(request.user),
    })


# Solo ADMIN y COORD crean/dirigen audiencia
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def comunicado_create(request):
    form = ComunicadoForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.autor = request.user
            obj.save()
            form.save_m2m()
            messages.success(request, "Comunicado creado correctamente.")
            return redirect("core:comunicados_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/comunicado_create.html", {"form": form})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def comunicado_edit(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)

    if not _is_admin_or_coord(request.user):
        return HttpResponse("No tienes permisos para editar este comunicado.", status=403)

    form = ComunicadoForm(request.POST or None, instance=com)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Comunicado actualizado.")
            return redirect("core:comunicados_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/comunicado_edit.html", {"form": form, "comunicado": com})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def comunicado_delete(request, comunicado_id):
    com = get_object_or_404(Comunicado, id=comunicado_id)
    if not _is_admin_or_coord(request.user):
        return HttpResponse("No tienes permisos para eliminar este comunicado.", status=403)
    com.delete()
    messages.success(request, "Comunicado eliminado.")
    return redirect("core:comunicados_list")


# =================== NOTICIAS (SOLO ADMIN) ===================
@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def noticias_list(request):
    """
    Listado con paginación para administración de noticias.
    """
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()  # "pub" | "nopub" | ""
    qs = Noticia.objects.all().order_by("-creado")  # <- FIX: 'creada' -> 'creado'
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(bajada__icontains=q))
    if estado == "pub":
        qs = qs.filter(publicada=True)
    elif estado == "nopub":
        qs = qs.filter(publicada=False)

    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    return render(request, "core/noticias_list.html", {
        "page_obj": page_obj,
        "q": q,
        "estado": estado,
    })


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def noticia_create(request):
    form = NoticiaForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.autor = request.user
            # si se marca publicada y no hay timestamp, lo definimos
            if obj.publicada and not obj.publicada_en:
                obj.publicada_en = timezone.now()
            obj.save()
            messages.success(request, "Noticia creada correctamente.")
            return redirect("core:noticias_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/noticia_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def noticia_edit(request, noticia_id: int):
    obj = get_object_or_404(Noticia, pk=noticia_id)
    form = NoticiaForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            prev_publicada = obj.publicada
            noticia = form.save(commit=False)
            # gestionar timestamp de publicación
            if noticia.publicada and not prev_publicada:
                noticia.publicada_en = timezone.now()
            if not noticia.publicada:
                noticia.publicada_en = None
            noticia.save()
            messages.success(request, "Noticia actualizada.")
            return redirect("core:noticias_list")
        messages.error(request, "Revisa los errores del formulario.")
    return render(request, "core/noticia_form.html", {"form": form, "is_edit": True, "obj": obj})


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def noticia_delete(request, noticia_id: int):
    obj = get_object_or_404(Noticia, pk=noticia_id)
    obj.delete()
    messages.success(request, "Noticia eliminada.")
    return redirect("core:noticias_list")


@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def noticia_toggle_publicar(request, noticia_id: int):
    """
    Publica/Despublica con un clic.
    """
    obj = get_object_or_404(Noticia, pk=noticia_id)
    obj.publicada = not obj.publicada
    obj.publicada_en = timezone.now() if obj.publicada else None
    obj.save(update_fields=["publicada", "publicada_en"])
    estado = "publicada" if obj.publicada else "despublicada"
    messages.success(request, f"Noticia {estado}.")
    return redirect("core:noticias_list")


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


# ------- Profesores (stubs mínimos) -------
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


# ================= PLANIFICACIONES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def planificaciones_list(request):
    try:
        base = date.fromisoformat(request.GET.get("semana") or "")
    except ValueError:
        base = timezone.localdate()
    lunes = _monday(base)

    programa = (request.GET.get("programa") or "").strip()
    sede_id = (request.GET.get("sede") or "")
    dep_id = (request.GET.get("disciplina") or "")
    curso_id = (request.GET.get("curso") or "")
    prof_id = (request.GET.get("prof") or "")

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
        form = PlanificacionUploadForm(request.POST, request.FILES, user=getattr(request, "user", None))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.semana = _monday(obj.semana)  # normaliza al lunes
            obj.autor = request.user

            existente = Planificacion.objects.filter(curso=obj.curso, semana=obj.semana).first()
            if existente:
                if existente.archivo:
                    PlanificacionVersion.objects.create(
                        planificacion=existente,
                        archivo=existente.archivo,
                        autor=request.user,
                    )
                existente.archivo = obj.archivo or existente.archivo
                existente.comentarios = getattr(obj, "comentarios", "")
                existente.publica = getattr(obj, "publica", False)
                existente.autor = request.user
                existente.save()
                messages.warning(request, f"Se creó versión {existente.versiones.count()+1} para esa semana.")
            else:
                obj.save()
                messages.success(request, f"Planificación de la semana {obj.semana:%d-%m-%Y} publicada.")
            return redirect("core:planificaciones_list")
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = PlanificacionUploadForm(user=request.user)

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


# ================= REPORTES =================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_home(request):
    return render(request, "core/reportes_home.html")


# 📆 Semanal de inasistencias
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

    # KPI
    asist = AsistenciaAtleta.objects.filter(clase__in=clases).select_related("atleta")
    total_presentes = asist.filter(presente=True).count()
    total_ausentes = asist.filter(presente=False).count()
    total_registros = total_presentes + total_ausentes
    alumnos_con_falta = asist.filter(presente=False).values_list("atleta_id", flat=True).distinct().count()

    # Alumnos con alerta (>= umbral faltas en la semana)
    alerta_ids = (
        asist.values("atleta_id")
        .annotate(faltas=Count("id", filter=Q(presente=False)))
        .filter(faltas__gte=umbral)
        .values_list("atleta_id", flat=True)
    )
    alumnos_alerta = len(list(alerta_ids))
    pct_asistencia = round((total_presentes / total_registros) * 100, 1) if total_registros else 0.0

    # Tabla principal agrupada por clase
    filas = []
    for c in clases.order_by("fecha", "hora_inicio"):
        qs = asist.filter(clase=c)
        presentes = qs.filter(presente=True).count()
        ausentes = qs.filter(presente=False).count()
        inscritos = presentes + ausentes
        pct = round((presentes / inscritos) * 100, 1) if inscritos else 0.0
        filas.append({
            "clase": c,
            "curso": getattr(c, "tema", "") or getattr(c.sede_deporte, "deporte", ""),
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
    faltas_semana = asist_semana.values("atleta_id").annotate(faltas=Count("id", filter=Q(presente=False)))
    faltas_map = {r["atleta_id"]: r["faltas"] for r in faltas_semana}

    for r in registros_clase:
        at = r.atleta
        nombre = at.usuario.get_full_name() if at and at.usuario_id else "—"
        rut = getattr(at, "rut", "—")
        tel_apod = getattr(getattr(at, "apoderado", None), "telefono", "") or ""
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


# 🧑‍🏫 Asistencia por clase (selector)
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET"])
def reporte_asistencia_por_clase(request):
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


# Placeholders
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_curso(request):
    return render(request, "core/reporte_placeholder.html", {"titulo": "Asistencia por curso (rango) – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_asistencia_por_sede(request):
    return render(request, "core/reporte_placeholder.html", {"titulo": "Asistencia por sede (rango) – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reporte_llegadas_tarde(request):
    return render(request, "core/reporte_placeholder.html", {"titulo": "Llegadas tarde – próximamente"})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
def reportes_exportar_todo(request):
    return HttpResponse("Exportador general (xlsx/pdf) – por implementar")


# ========= Utilidades de ubicación / QR =========
def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


def _nearest_sede(lat, lng):
    sedes = Sede.objects.exclude(Q(latitud__isnull=True) | Q(longitud__isnull=True))
    best, best_d = None, None
    for s in sedes:
        d = _haversine_m(lat, lng, s.latitud, s.longitud)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


@login_required
@require_http_methods(["GET", "POST"])
def mi_asistencia_qr(request):
    if not _es_prof(request.user):
        return HttpResponseForbidden("Solo profesores.")
    try:
        from applications.profesor.models import AsistenciaProfesor
    except Exception:
        return HttpResponse("Función no disponible: falta el modelo AsistenciaProfesor.", status=501)

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
        action = request.POST.get("action")            # 'entrada' | 'salida'
        qr_text = request.POST.get("qr_text", "").strip()
        lat_str = request.POST.get("geo_lat")
        lng_str = request.POST.get("geo_lng")

        sede = None

        if qr_text.startswith("SEDE:"):
            try:
                sede_id = int(qr_text.split(":", 1)[1])
                sede = Sede.objects.filter(pk=sede_id).first()
            except ValueError:
                sede = None

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
            tipo = (AsistenciaProfesor.Tipo.ENTRADA if action == "entrada"
                    else AsistenciaProfesor.Tipo.SALIDA)

            ya_existe = AsistenciaProfesor.objects.filter(
                usuario=request.user, fecha=hoy, tipo=tipo
            ).exists()

            if ya_existe:
                mensaje = "Ya registraste tu entrada hoy." if tipo == AsistenciaProfesor.Tipo.ENTRADA \
                    else "Ya registraste tu salida hoy."
            else:
                AsistenciaProfesor.objects.create(
                    usuario=request.user, sede=sede, fecha=hoy, hora=ahora, tipo=tipo
                )
                ok = True
                hhmm = timezone.localtime().strftime("%H:%M")
                pref = "Entrada" if tipo == AsistenciaProfesor.Tipo.ENTRADA else "Salida"
                mensaje = f"{pref} registrada correctamente — {hhmm} en {sede.nombre}"

    return render(request, "profesor/mi_asistencia_qr.html", {
        "ultima_entrada": ultima_entrada,
        "ultima_salida":  ultima_salida,
        "mensaje":        mensaje,
        "ok":             ok,
    })


# ====== Asistencia (stubs para rutas) ======
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_profesor(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia PROFESOR curso_id={curso_id} (GET) -> pantalla tomar asistencia")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, Usuario.Tipo.PROF)
@require_http_methods(["GET", "POST"])
def asistencia_estudiantes(request, curso_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (POST) -> registrada")
    return HttpResponse(f"CORE / Asistencia ESTUDIANTES curso_id={curso_id} (GET) -> lista alumnos")


# ====== Ficha estudiante (stub) ======
@role_required(Usuario.Tipo.PROF, Usuario.Tipo.PMUL, Usuario.Tipo.COORD, Usuario.Tipo.ADMIN)
@require_http_methods(["GET", "POST"])
def ficha_estudiante(request, estudiante_id: int):
    if request.method == "POST":
        return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (POST) -> observación agregada")
    return HttpResponse(f"CORE / Ficha estudiante_id={estudiante_id} (GET) -> ver ficha + historial")
