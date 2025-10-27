from django.urls import path
from . import views
from applications.usuarios import views_profesor as vp  # 👈 importamos las vistas ya existentes

app_name = "profesor"

urlpatterns = [
    # rutas que ya tenías en usuarios (las reutilizamos)
    path("panel/", vp.panel_profesor, name="panel_profesor"),
    path("cursos/", vp.mis_cursos, name="mis_cursos_prof"),
    path("asistencia/", vp.asistencia_listado, name="asistencia_profesor"),
    path("asistencia/<int:curso_id>/", vp.asistencia_tomar, name="asistencia_tomar"),
    path("planificaciones/", vp.planificaciones, name="planificaciones_prof"),
    path("comunicados/", vp.comunicados, name="comunicados_prof"),
    path("perfil/", vp.mi_perfil, name="perfil_profesor"),

    # rutas nuevas del módulo profesor (QR + historial)
    path("mi-asistencia/", views.mi_asistencia_qr, name="mi_asistencia_qr"),
    path("mi-asistencia/historial/", views.mi_historial_asistencia, name="mi_historial_asistencia"),
    path("sedes/qr/", views.sedes_qr_list, name="sedes_qr_list"),
    path("sedes/<int:sede_id>/qr.png", views.qr_sede_png, name="qr_sede_png"),
    path("sedes/<int:sede_id>/placard/", views.placard_sede_qr, name="placard_sede_qr"),
]