# applications/core/services/reportes_service.py
from datetime import date, timedelta
from django.db.models import Count, Q, F
from django.db.models.functions import TruncMonth, ExtractYear
from applications.core.models import (
    Estudiante, Curso, Sede, Planificacion,
    AsistenciaCurso, AsistenciaCursoDetalle
)
from applications.usuarios.models import Usuario, Profesor

# ================================================================
# 📊 FUNCIÓN PRINCIPAL DE KPI
# ================================================================
def obtener_kpi_generales():
    """Obtiene los principales indicadores generales del programa CPC."""
    total_estudiantes = Estudiante.objects.count()
    activos = Estudiante.objects.filter(activo=True).count()
    total_profesores = Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF).count()
    total_cursos = Curso.objects.filter(publicado=True).count()
    total_sedes = Sede.objects.filter(activa=True).count()
    total_planificaciones = Planificacion.objects.count()

    # Asistencias
    presentes = AsistenciaCursoDetalle.objects.filter(estado="P").count()
    total_detalles = AsistenciaCursoDetalle.objects.count()
    asistencia_promedio = round((presentes / total_detalles) * 100, 1) if total_detalles else 0

    # Género
    mujeres = Estudiante.objects.filter(genero__iexact="F").count()
    hombres = Estudiante.objects.filter(genero__iexact="M").count()
    total_genero = mujeres + hombres
    equidad_genero = round((mujeres / total_genero) * 100, 1) if total_genero else 0

    # KPI anuales (año actual)
    hoy = date.today()
    año_actual = hoy.year
    nuevos_estudiantes = Estudiante.objects.filter(creado__year=año_actual).count()
    cursos_activos = Curso.objects.filter(fecha_inicio__year=año_actual).count()
    planificaciones_anuales = Planificacion.objects.filter(creado__year=año_actual).count()

    return [
        {"label": "Estudiantes activos", "value": activos, "icon": "fa-users", "color": "#3b82f6"},
        {"label": "Profesores", "value": total_profesores, "icon": "fa-user-tie", "color": "#10b981"},
        {"label": "Cursos activos", "value": total_cursos, "icon": "fa-book-open", "color": "#6366f1"},
        {"label": "Sedes activas", "value": total_sedes, "icon": "fa-building", "color": "#f59e0b"},
        {"label": "Planificaciones", "value": total_planificaciones, "icon": "fa-file-alt", "color": "#84cc16"},
        {"label": "Asistencia promedio", "value": f"{asistencia_promedio}%", "icon": "fa-clipboard-check", "color": "#10b981"},
        {"label": "Equidad de género (♀)", "value": f"{equidad_genero}%", "icon": "fa-venus-mars", "color": "#ec4899"},
        {"label": "Nuevos estudiantes " + str(año_actual), "value": nuevos_estudiantes, "icon": "fa-user-plus", "color": "#2563eb"},
        {"label": "Cursos iniciados " + str(año_actual), "value": cursos_activos, "icon": "fa-calendar", "color": "#0284c7"},
        {"label": "Planificaciones " + str(año_actual), "value": planificaciones_anuales, "icon": "fa-folder-open", "color": "#0ea5e9"},
    ]


# ================================================================
# 📅 KPI MENSUALES
# ================================================================
def obtener_kpi_mensuales():
    """Devuelve datos agregados mensualmente para gráficos."""
    estudiantes_por_mes = (
        Estudiante.objects.annotate(mes=TruncMonth("creado"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    asistencias_por_mes = (
        AsistenciaCurso.objects.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    meses_labels = [e["mes"].strftime("%b %Y") for e in estudiantes_por_mes]
    datos_estudiantes = [e["total"] for e in estudiantes_por_mes]
    datos_asistencias = [a["total"] for a in asistencias_por_mes]

    return meses_labels, datos_estudiantes, datos_asistencias


# ================================================================
# 🧑‍🏫 KPI POR PROFESOR
# ================================================================
def obtener_kpi_profesores():
    """Devuelve métricas de actividad docente."""
    profesores = Profesor.objects.all().annotate(
        total_cursos=Count("usuario__cursos_impartidos"),
        total_planificaciones=Count("usuario__planificacion"),
    )
    data = []
    for p in profesores:
        data.append({
            "nombre": str(p.usuario),
            "cursos": p.total_cursos,
            "planificaciones": p.total_planificaciones,
        })
    return data


# ================================================================
# 🏟️ KPI POR SEDE
# ================================================================
def obtener_kpi_por_sede():
    """Cantidad de cursos y estudiantes por sede."""
    sedes = Sede.objects.annotate(
        total_cursos=Count("curso"),
        total_estudiantes=Count("curso__estudiante"),
    )
    data = []
    for s in sedes:
        data.append({
            "sede": s.nombre,
            "cursos": s.total_cursos,
            "estudiantes": s.total_estudiantes,
        })
    return data
