from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # ===== Home + páginas públicas =====
    path("", views.home, name="home"),
    path("procesos-inscripcion/", views.procesos_inscripcion, name="procesos_inscripcion"),
    path("procesos/", views.procesos_inscripcion, name="procesos"),  # alias compat
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
    path("estudiantes/<int:estudiante_id>/activar/", views.estudiante_activar, name="estudiante_activar"),
    path("estudiantes/<int:estudiante_id>/desactivar/", views.estudiante_desactivar, name="estudiante_desactivar"),
    path("estudiantes/mios/", views.estudiantes_list_prof, name="estudiantes_list_prof"),
path("estudiantes/<int:pk>/", views.estudiante_detail, name="estudiante_detail"),
path("estudiantes/<int:pk>/pdf/", views.estudiante_detail_pdf, name="estudiante_detail_pdf"),

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
    path("comunicados/", views.comunicados_public, name="comunicado_public"),
    path("comunicados/<int:pk>/", views.comunicado_public_detail, name="comunicado_public_detail"),

    # === Panel (ADMIN/COORD) ===
    path("panel/comunicados/", views.comunicados_list, name="comunicados_list"),
    path("panel/comunicados/nuevo/", views.comunicado_create, name="comunicado_create"),
    path("panel/comunicados/<int:comunicado_id>/editar/", views.comunicado_edit, name="comunicado_edit"),
    path("panel/comunicados/<int:comunicado_id>/eliminar/", views.comunicado_delete, name="comunicado_delete"),
    # ===== Planificaciones =====
    path("planificaciones/", views.planificaciones_list, name="planificaciones_list"),
    path("planificaciones/upload/", views.planificacion_upload, name="planificacion_upload"),
    path("planificaciones/<int:plan_id>/", views.planificacion_detail, name="planificacion_detail"),
    path("planificaciones/<int:plan_id>/download/", views.planificacion_download, name="planificacion_download"),
    path("planificaciones/<int:plan_id>/historial/", views.planificacion_historial, name="planificacion_historial"),

    # ===== Asistencia =====
    path("asistencia/<int:curso_id>/tomar/", views.asistencia_tomar, name="asistencia_tomar"),          # canónica
    path("asistencia/profesor/<int:curso_id>/", views.asistencia_tomar, name="asistencia_profesor"),   # alias legacy
    path("asistencia/estudiantes/<int:curso_id>/", views.asistencia_estudiantes, name="asistencia_estudiantes"),
    path("asistencias/semaforo/", views.asistencia_semaforo, name="asistencia_semaforo"),
    path("profesor/mi-asistencia-qr/", views.mi_asistencia_qr, name="mi_asistencia_qr"),

    # ===== KPI / Reportes =====
    # Tableros
    path("reportes/kpi/", views.dashboard_kpi, name="dashboard_kpi"),
    path("reportes/kpi/semanal/", views.dashboard_kpi_semana, name="dashboard_kpi_semana"),
    path("reportes/kpi/mensual/", views.dashboard_kpi_mes, name="dashboard_kpi_mes"),
    path("reportes/kpi/anual/", views.dashboard_kpi_anio, name="dashboard_kpi_anio"),

    # Exportaciones (GENERAL)
    path("reportes/exportar/general/pdf/", views.exportar_kpi_general_pdf, name="exportar_kpi_general_pdf"),
    path("reportes/exportar/general/excel/", views.exportar_kpi_general_excel, name="exportar_kpi_general_excel"),
    # Exportaciones (SEMANA)
    path("reportes/exportar/semana/pdf/", views.exportar_kpi_semana_pdf, name="exportar_kpi_semana_pdf"),
    path("reportes/exportar/semana/excel/", views.exportar_kpi_semana_excel, name="exportar_kpi_semana_excel"),
    # Exportaciones (MES)
    path("reportes/exportar/mes/pdf/", views.exportar_kpi_mes_pdf, name="exportar_kpi_mes_pdf"),
    path("reportes/exportar/mes/excel/", views.exportar_kpi_mes_excel, name="exportar_kpi_mes_excel"),
    # Exportaciones (AÑO)
    path("reportes/exportar/anio/pdf/", views.exportar_kpi_anio_pdf, name="exportar_kpi_anio_pdf"),
    path("reportes/exportar/anio/excel/", views.exportar_kpi_anio_excel, name="exportar_kpi_anio_excel"),

    # ===== Noticias (solo ADMIN) =====
    path("noticias/", views.noticias_list, name="noticias_list"),
    path("noticias/nueva/", views.noticia_create, name="noticia_create"),
    path("noticias/<int:noticia_id>/editar/", views.noticia_edit, name="noticia_edit"),
    path("noticias/<int:noticia_id>/eliminar/", views.noticia_delete, name="noticia_delete"),
    path("noticias/<int:noticia_id>/toggle/", views.noticia_toggle_publicar, name="noticia_toggle_publicar"),

    # ===== Registro público =====
    path("registro/", views.registro_publico, name="registro_publico"),

    # ===== Solicitudes (detectadas por RegistroPublicoForm) =====
    path("solicitudes/", views.solicitudes_list, name="solicitudes_list"),
    path("solicitudes/<int:pk>/", views.solicitud_detail, name="solicitud_detail"),
    path("solicitudes/<int:pk>/gestionar/", views.solicitud_marcar_gestionada, name="solicitud_marcar_gestionada"),

    # ===== Postulaciones (admin) =====
    path("postulaciones/", views.registro_list, name="registro_list"),
    path("postulaciones/<int:pk>/", views.registro_detail, name="registro_detail"),

    # ===== Períodos de postulación (admin) =====
    path("postulaciones/periodos/", views.periodos_list, name="periodos_list"),
    path("postulaciones/periodos/nuevo/", views.periodo_create, name="periodo_create"),
    path("postulaciones/periodos/<int:periodo_id>/editar/", views.periodo_edit, name="periodo_edit"),
    path("postulaciones/periodos/<int:periodo_id>/toggle-activo/", views.periodo_toggle_activo, name="periodo_toggle_activo"),
    path("postulaciones/periodos/<int:periodo_id>/set-estado/", views.periodo_set_estado, name="periodo_set_estado"),
    path("postulaciones/periodos/<int:periodo_id>/cerrar-hoy/", views.periodo_cerrar_hoy, name="periodo_cerrar_hoy"),

    # ===== Mis cursos (perfil profesor) =====
    path("cursos/mios/", views.cursos_mios, name="cursos_mios"),

    # ===== Catálogo deportes =====
    path("deportes/", views.deportes_list, name="deportes_list"),
path("deportes/nuevo/", views.deporte_create, name="deporte_create"),
path("deportes/<int:id>/editar/", views.deporte_edit, name="deporte_edit"),
    path("deportes/<int:id>/eliminar/", views.deporte_delete, name="deporte_delete"),
]
