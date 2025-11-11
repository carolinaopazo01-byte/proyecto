from django.urls import path
from . import views
from applications.usuarios import views_profesor as vp
from applications.core import views as core_views   # << aquí

app_name = "profesor"

urlpatterns = [
    path("panel/", vp.panel_profesor, name="panel_profesor"),
    path("miscursos/", vp.mis_cursos, name="mis_cursos_prof"),


    path("asistencia/", core_views.asistencia_listado_por_curso, name="asistencia_profesor"),
    path("asistencia/<int:curso_id>/", core_views.asistencia_tomar, name="asistencia_tomar"),
path("cursos/<int:curso_id>/asistencia/historial/", views.asistencia_historial, name="asistencia_historial"),

    path("planificaciones/", vp.planificaciones, name="planificaciones"),
    path("comunicados/", vp.comunicados, name="comunicados_prof"),
    path("perfil/", vp.mi_perfil, name="perfil_profesor"),

    path("mi-asistencia/", views.mi_asistencia_qr, name="mi_asistencia_qr"),
    path("mi-asistencia/historial/", views.mi_historial_asistencia, name="mi_historial_asistencia"),
    path("sedes/qr/", views.sedes_qr_list, name="sedes_qr_list"),
    path("sedes/<int:sede_id>/qr.png", views.qr_sede_png, name="qr_sede_png"),
    path("sedes/<int:sede_id>/placard/", views.placard_sede_qr, name="placard_sede_qr"),
    path("alumnos/temporal/nuevo/", views.alumno_temporal_new, name="alumno_temporal_new"),
]
