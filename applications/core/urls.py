from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Home + páginas públicas
    path("", views.home, name="home"),
    path("quienes-somos/", views.quienes_somos, name="quienes"),
    path("procesos-inscripcion/", views.procesos_inscripcion, name="procesos"),
    path("deportes-y-recintos/", views.deportes_recintos, name="deportes"),
    path("equipo-multidisciplinario/", views.equipo_multidisciplinario, name="equipo"),

    # Estudiantes
    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("estudiantes/nuevo/", views.estudiante_create, name="estudiante_create"),
    path("estudiantes/<int:estudiante_id>/editar/", views.estudiante_edit, name="estudiante_edit"),
    path("estudiantes/<int:estudiante_id>/eliminar/", views.estudiante_delete, name="estudiante_delete"),

    # Cursos
    path("cursos/", views.cursos_list, name="cursos_list"),
    path("cursos/nuevo/", views.curso_create, name="curso_create"),
    path("cursos/<int:curso_id>/editar/", views.curso_edit, name="curso_edit"),
    path("cursos/<int:curso_id>/eliminar/", views.curso_delete, name="curso_delete"),
    path("cursos/<int:curso_id>/configurar-cupos/", views.curso_configurar_cupos, name="curso_configurar_cupos"),

    # Sedes
    path("sedes/", views.sedes_list, name="sedes_list"),
    path("sedes/nuevo/", views.sede_create, name="sede_create"),
    path("sedes/<int:sede_id>/editar/", views.sede_edit, name="sede_edit"),
    path("sedes/<int:sede_id>/eliminar/", views.sede_delete, name="sede_delete"),

    # Comunicados
    path("comunicados/", views.comunicados_list, name="comunicados_list"),
    path("comunicados/nuevo/", views.comunicado_create, name="comunicado_create"),
    path("comunicados/<int:comunicado_id>/editar/", views.comunicado_edit, name="comunicado_edit"),
    path("comunicados/<int:comunicado_id>/eliminar/", views.comunicado_delete, name="comunicado_delete"),

    # Planificaciones
    path("planificaciones/", views.planificaciones_list, name="planificaciones_list"),
    path("planificaciones/nuevo/", views.planificacion_create, name="planificacion_create"),
    path("planificaciones/<int:plan_id>/editar/", views.planificacion_edit, name="planificacion_edit"),
    path("planificaciones/<int:plan_id>/eliminar/", views.planificacion_delete, name="planificacion_delete"),
    path("planificaciones/upload/", views.planificacion_upload, name="planificacion_upload"),

    # Asistencia (stubs)
    path("asistencia/profesor/<int:curso_id>/", views.asistencia_profesor, name="asistencia_profesor"),
    path("asistencia/estudiantes/<int:curso_id>/", views.asistencia_estudiantes, name="asistencia_estudiantes"),

    # Ficha estudiante (stub)
    path("ficha-estudiante/<int:estudiante_id>/", views.ficha_estudiante, name="ficha_estudiante"),

    # Reportes
    path("reportes/", views.reportes_home, name="reportes_home"),
    path("reportes/inasistencias/", views.reporte_inasistencias, name="reporte_inasistencias"),
    path("reportes/asistencia-clase/<int:clase_id>/", views.reporte_asistencia_por_clase, name="reporte_asistencia_por_clase"),

    # Deportes
    path("deportes/catalogo/", views.deportes_list, name="deportes_list"),
    path("deportes/nuevo/", views.deporte_create, name="deporte_create"),
    path("deportes/<int:deporte_id>/editar/", views.deporte_edit, name="deporte_edit"),
    path("deportes/<int:deporte_id>/eliminar/", views.deporte_delete, name="deporte_delete"),
]
