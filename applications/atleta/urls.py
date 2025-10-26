# applications/atleta/urls.py
from django.urls import path
from . import views

app_name = "atleta"

urlpatterns = [
    path("agenda/", views.agenda_disponible, name="agenda_disponible"),
    path("citas/nueva/", views.cita_crear, name="cita_crear"),
    path("proceso/ingreso-ar/", views.proceso_ingreso_alto_rendimiento, name="proceso_ingreso_ar"),
    path("panel/", views.panel, name="panel"),

    # NUEVO
    path("mis-cursos/", views.mis_cursos, name="mis_cursos"),
    path("asistencia/", views.asistencia_semana, name="asistencia_semana"),
    path("planificacion/", views.planificacion_semana, name="planificacion_semana"),
    path("documentos/", views.documentos_protocolos, name="documentos_protocolos"),
    path("password/", views.cambiar_password, name="cambiar_password"),
]
