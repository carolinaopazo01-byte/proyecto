from django.urls import path
from . import views
from .views import (
    planificaciones_list,
    planificacion_upload,
    planificacion_detail,
    planificacion_download,
)

app_name = "core"

urlpatterns = [
    # ===== Home + páginas públicas =====
    path("", views.home, name="home"),
    path("quienes-somos/", views.quienes_somos, name="quienes"),
    # nombre "oficial"
    path("procesos-inscripcion/", views.procesos_inscripcion, name="procesos_inscripcion"),
    # alias para compatibilidad con templates antiguos ({% url 'core:procesos' %})
    path("procesos-inscripcion/", views.procesos_inscripcion, name="procesos"),
    path("deportes-y-recintos/", views.deportes_recintos, name="deportes"),
    path("equipo-multidisciplinario/", views.equipo_multidisciplinario, name="equipo"),

    # ===== Estudiantes =====
    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("estudiantes/nuevo/selector/", views.estudiante_nuevo_selector, name="estudiante_nuevo_selector"),
    path("estudiantes/nuevo/formativo/", views.estudiante_create_formativo, name="estudiante_create_formativo"),
    path("estudiantes/nuevo/alto/", views.estudiante_create_alto, name="estudiante_create_alto"),
    path("estudiantes/nuevo/", views.estudiante_create, name="estudiante_create"),
    path("estudiantes/<int:estudiante_id>/editar/", views.estudiante_edit, name="estudiante_edit"),
    path("estudiantes/<int:estudiante_id>/eliminar/", views.estudiante_delete, name="estudiante_delete"),

    # ===== Cursos =====
    path("cursos/", views.cursos_list, name="cursos_list"),
    path("cursos/nuevo/", views.curso_create, name="curso_create"),
    path("cursos/<int:curso_id>/editar/", views.curso_edit, name="curso_edit"),
    path("cursos/<int:curso_id>/eliminar/", views.curso_delete, name="curso_delete"),
    path("cursos/<int:curso_id>/configurar-cupos/", views.curso_configurar_cupos, name="curso_configurar_cupos"),
    path("cursos/<int:curso_id>/inscribir/<int:estudiante_id>/", views.inscribir_en_curso, name="inscribir_en_curso"),

    # ===== Sedes =====
    path("sedes/", views.sedes_list, name="sedes_list"),
    path("sedes/nuevo/", views.sede_create, name="sede_create"),
    path("sedes/<int:sede_id>/", views.sede_detail, name="sede_detail"),
    path("sedes/<int:sede_id>/editar/", views.sede_edit, name="sede_edit"),
    path("sedes/<int:sede_id>/eliminar/", views.sede_delete, name="sede_delete"),

    # ===== Comunicados =====
    path("comunicados/", views.comunicados_list, name="comunicados_list"),
    path("comunicados/nuevo/", views.comunicado_create, name="comunicado_create"),
    path("comunicados/<int:comunicado_id>/editar/", views.comunicado_edit, name="comunicado_edit"),
    path("comunicados/<int:comunicado_id>/eliminar/", views.comunicado_delete, name="comunicado_delete"),

    # ===== Planificaciones =====
    path("planificaciones/", planificaciones_list, name="planificaciones_list"),
    path("planificaciones/upload/", planificacion_upload, name="planificacion_upload"),
    path("planificaciones/<int:plan_id>/", planificacion_detail, name="planificacion_detail"),
    path("planificaciones/<int:plan_id>/download/", planificacion_download, name="planificacion_download"),
    path("planificaciones/<int:plan_id>/historial/", views.planificacion_historial, name="planificacion_historial"),

    # ===== Asistencia (stubs) =====
    path("asistencia/profesor/<int:curso_id>/", views.asistencia_profesor, name="asistencia_profesor"),
    path("asistencia/estudiantes/<int:curso_id>/", views.asistencia_estudiantes, name="asistencia_estudiantes"),

    # ===== Ficha estudiante (stub) =====
    path("ficha-estudiante/<int:estudiante_id>/", views.ficha_estudiante, name="ficha_estudiante"),

    # ===== Reportes =====
    path("reportes/", views.reportes_home, name="reportes_home"),
    path("reportes/inasistencias/", views.reporte_inasistencias, name="reporte_inasistencias"),
    path("reportes/inasistencias/detalle/<int:clase_id>/", views.reporte_inasistencias_detalle, name="reporte_inasistencias_detalle"),
    path("reportes/inasistencias/export.csv", views.reporte_inasistencias_export_csv, name="reporte_inasistencias_export"),
    path("reportes/asistencia-clase/", views.reporte_asistencia_por_clase, name="reporte_asistencia_por_clase"),
    path("reportes/asistencia-curso/", views.reporte_asistencia_por_curso, name="reporte_asistencia_por_curso"),
    path("reportes/asistencia-sede/", views.reporte_asistencia_por_sede, name="reporte_asistencia_por_sede"),
    path("reportes/llegadas-tarde/", views.reporte_llegadas_tarde, name="reporte_llegadas_tarde"),
    path("reportes/exportar-todo/", views.reportes_exportar_todo, name="reportes_exportar_todo"),

    # ===== Deportes =====
    path("deportes/", views.deportes_list, name="deportes_list"),
    path("deportes/nuevo/", views.deporte_create, name="deporte_create"),
    path("deportes/<int:deporte_id>/editar/", views.deporte_edit, name="deporte_edit"),
    path("deportes/<int:deporte_id>/eliminar/", views.deporte_delete, name="deporte_delete"),

    # ===== Noticias (solo ADMIN) =====
    path("noticias/", views.noticias_list, name="noticias_list"),
    path("noticias/nueva/", views.noticia_create, name="noticia_create"),
    path("noticias/<int:noticia_id>/editar/", views.noticia_edit, name="noticia_edit"),
    path("noticias/<int:noticia_id>/eliminar/", views.noticia_delete, name="noticia_delete"),
    path("noticias/<int:noticia_id>/toggle/", views.noticia_toggle_publicar, name="noticia_toggle_publicar"),

    # ===== Registro público (formulario) =====
    path("registro/", views.registro_publico, name="registro_publico"),

    # ===== Solicitudes (genéricas detectadas por RegistroPublicoForm) =====
    path("solicitudes/", views.solicitudes_list, name="solicitudes_list"),
    path("solicitudes/<int:pk>/", views.solicitud_detail, name="solicitud_detail"),
    path("solicitudes/<int:pk>/gestionar/", views.solicitud_marcar_gestionada, name="solicitud_marcar_gestionada"),

    # ===== Postulaciones (admin) — templates: registro_list / registro_detail =====
    path("postulaciones/", views.registro_list, name="registro_list"),
    path("postulaciones/<int:pk>/", views.registro_detail, name="registro_detail"),

    # ===== Períodos de postulación (admin) =====
    path("postulaciones/periodos/", views.periodos_list, name="periodos_list"),
    path("postulaciones/periodos/nuevo/", views.periodo_create, name="periodo_create"),
    path("postulaciones/periodos/<int:periodo_id>/editar/", views.periodo_edit, name="periodo_edit"),
    path("postulaciones/periodos/<int:periodo_id>/toggle-activo/", views.periodo_toggle_activo, name="periodo_toggle_activo"),
    path("postulaciones/periodos/<int:periodo_id>/set-estado/", views.periodo_set_estado, name="periodo_set_estado"),
    path("postulaciones/periodos/<int:periodo_id>/cerrar-hoy/", views.periodo_cerrar_hoy, name="periodo_cerrar_hoy"),
]
