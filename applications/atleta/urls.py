# applications/atleta/urls.py
from django.urls import path
from . import views

app_name = "atleta"

urlpatterns = [
    # Panel y navegación general
    path("panel/", views.panel, name="panel"),

    # Cursos / Asistencia / Planificación / Documentos
    path("mis-cursos/", views.mis_cursos, name="mis_cursos"),
    path("asistencia/", views.asistencia_semana, name="asistencia_semana"),
    path("planificacion/", views.planificacion_semana, name="planificacion_semana"),
    path("documentos/", views.documentos_protocolos, name="documentos_protocolos"),

    # Fichas del atleta (lectura)
    path("mis-fichas/", views.mis_fichas, name="mis_fichas"),

    # Agenda PMUL para atletas: ver horas y reservar
    path("horas/", views.horas_disponibles, name="horas_disponibles"),
    path("horas/<int:slot_id>/reservar/", views.reservar_hora, name="reservar_hora"),

    # Citas del atleta: listado y cancelar
    path("mis-citas/", views.mis_citas, name="mis_citas"),
    path("cita/<int:cita_id>/cancelar/", views.cita_cancelar, name="cita_cancelar"),


path("horas/", views.horas_disponibles, name="horas_disponibles"),
    path("agenda/", views.agenda_disponible, name="agenda_disponible"),
    path("citas/nueva/", views.cita_crear, name="cita_crear"),
    path("proceso/ingreso-ar/", views.proceso_ingreso_alto_rendimiento, name="proceso_ingreso_ar"),

    #contraseña
    path("cuenta/cambiar-password/", views.cambiar_password, name="cambiar_password"),
]
