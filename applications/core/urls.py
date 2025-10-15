from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),

    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("estudiantes/nuevo/", views.estudiante_create, name="estudiante_create"),

    path("cursos/", views.cursos_list, name="cursos_list"),
    path("cursos/nuevo/", views.curso_create, name="curso_create"),
    path("cursos/<int:curso_id>/cupos/", views.curso_configurar_cupos, name="curso_configurar_cupos"),
    path("cursos/<int:curso_id>/editar/", views.curso_edit, name="curso_edit"),
    path("cursos/<int:curso_id>/eliminar/", views.curso_delete, name="curso_delete"),

    path("profesores/", views.profesores_list, name="profesores_list"),
    path("profesores/nuevo/", views.profesor_create, name="profesor_create"),

    path("planificacion/subir/", views.planificacion_upload, name="planificacion_upload"),

    path("login/", views.login_view, name="login"),
    path("recuperar-password/", views.recuperar_password, name="recuperar_password"),

    path("asistencia/profesor/<int:curso_id>/", views.asistencia_profesor, name="asistencia_profesor"),
    path("asistencia/estudiantes/<int:curso_id>/", views.asistencia_estudiantes, name="asistencia_estudiantes"),

    path("fichas/<int:estudiante_id>/", views.ficha_estudiante, name="ficha_estudiante"),

    path("comunicados/", views.comunicados_list, name="comunicados_list"),
    path("comunicados/nuevo/", views.comunicado_create, name="comunicado_create"),
    path("comunicados/<int:comunicado_id>/editar/", views.comunicado_edit, name="comunicado_edit"),
    path("comunicados/<int:comunicado_id>/eliminar/", views.comunicado_delete, name="comunicado_delete"),

    path("reportes/inasistencias/", views.reporte_inasistencias, name="reporte_inasistencias"),
    path("reportes/asistencia/clase/<int:clase_id>/", views.reporte_asistencia_por_clase, name="reporte_asistencia_por_clase"),

    path("sedes/", views.sedes_list, name="sedes_list"),
    path("sedes/nueva/", views.sede_create, name="sede_create"),
    path("sedes/<int:sede_id>/editar/", views.sede_edit, name="sede_edit"),
    path("sedes/<int:sede_id>/eliminar/", views.sede_delete, name="sede_delete"),

    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("estudiantes/nuevo/", views.estudiante_create, name="estudiante_create"),
    path("estudiantes/<int:estudiante_id>/editar/", views.estudiante_edit, name="estudiante_edit"),
    path("estudiantes/<int:estudiante_id>/eliminar/", views.estudiante_delete, name="estudiante_delete"),

# Informativas
path("quienes-somos/", views.quienes_somos, name="quienes"),
path("procesos-inscripcion/", views.procesos_inscripcion, name="procesos"),
path("deportes-recintos/", views.deportes_recintos, name="deportes"),
path("equipo-multidisciplinario/", views.equipo_multidisciplinario, name="equipo"),

]
