from django.urls import path
from . import views
from .views import (
    planificaciones_list,
    planificacion_upload,
    planificacion_detail,      # opcional
    planificacion_download,    # opcional
)
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
    path("sedes/<int:sede_id>/", views.sede_detail, name="sede_detail"),
    path("sedes/<int:sede_id>/editar/", views.sede_edit, name="sede_edit"),
    path("sedes/<int:sede_id>/eliminar/", views.sede_delete, name="sede_delete"),

    # Comunicados
    path("comunicados/", views.comunicados_list, name="comunicados_list"),
    path("comunicados/nuevo/", views.comunicado_create, name="comunicado_create"),
    path("comunicados/<int:comunicado_id>/editar/", views.comunicado_edit, name="comunicado_edit"),
    path("comunicados/<int:comunicado_id>/eliminar/", views.comunicado_delete, name="comunicado_delete"),

    # Planificaciones
    #path("planificaciones/upload/", views.planificacion_upload, name="planificacion_upload"),
    #path("planificaciones/", views.planificaciones_list, name="planificaciones_list"),
    #path("planificaciones/<int:plan_id>/", views.planificacion_detail, name="planificacion_detail"),
    #path("planificaciones/<int:plan_id>/download/", views.planificacion_download, name="planificacion_download"),
    #path("planificaciones/<int:plan_id>/historial/", views.planificacion_historial, name="planificacion_historial"),
    path("planificaciones/", planificaciones_list, name="planificaciones_list"),
    path("planificaciones/upload/", planificacion_upload, name="planificacion_upload"),
    path("planificaciones/<int:plan_id>/", planificacion_detail, name="planificacion_detail"),
    path("planificaciones/<int:plan_id>/download/", planificacion_download, name="planificacion_download"),
    path("planificaciones/<int:plan_id>/historial/", views.planificacion_historial, name="planificacion_historial"),
    # Asistencia (stubs)
    path("asistencia/profesor/<int:curso_id>/", views.asistencia_profesor, name="asistencia_profesor"),
    path("asistencia/estudiantes/<int:curso_id>/", views.asistencia_estudiantes, name="asistencia_estudiantes"),

    # Ficha estudiante (stub)
    path("ficha-estudiante/<int:estudiante_id>/", views.ficha_estudiante, name="ficha_estudiante"),

    # --- REPORTES ---
    path("reportes/", views.reportes_home, name="reportes_home"),

    # 📆 Semanal de inasistencias
    path("reportes/inasistencias/", views.reporte_inasistencias, name="reporte_inasistencias"),
    path("reportes/inasistencias/detalle/<int:clase_id>/", views.reporte_inasistencias_detalle,
         name="reporte_inasistencias_detalle"),
    path("reportes/inasistencias/export.csv", views.reporte_inasistencias_export_csv,
         name="reporte_inasistencias_export"),

    # 🧑‍🏫 Asistencia por clase (selector)
    path("reportes/asistencia-clase/", views.reporte_asistencia_por_clase, name="reporte_asistencia_por_clase"),

    # Placeholders (pantallas en blanco listas para implementar)
    path("reportes/asistencia-curso/", views.reporte_asistencia_por_curso, name="reporte_asistencia_por_curso"),
    path("reportes/asistencia-sede/", views.reporte_asistencia_por_sede, name="reporte_asistencia_por_sede"),
    path("reportes/llegadas-tarde/", views.reporte_llegadas_tarde, name="reporte_llegadas_tarde"),
    path("reportes/exportar-todo/", views.reportes_exportar_todo, name="reportes_exportar_todo"),

    # Deportes
    path("deportes/", views.deportes_list, name="deportes_list"),
    path("deportes/nuevo/", views.deporte_create, name="deporte_create"),
    path("deportes/<int:deporte_id>/editar/", views.deporte_edit, name="deporte_edit"),
    path("deportes/<int:deporte_id>/eliminar/", views.deporte_delete, name="deporte_delete"),
]