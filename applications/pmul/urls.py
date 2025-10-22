from django.urls import path
from . import views

app_name = "pmul"

urlpatterns = [
    path("", views.panel, name="panel"),

    # Agenda
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/nueva/", views.cita_new, name="cita_new"),
    path("agenda/<int:cita_id>/editar/", views.cita_edit, name="cita_edit"),
    path("agenda/<int:cita_id>/cancelar/", views.cita_cancel, name="cita_cancel"),
    path("agenda/<int:cita_id>/reprogramar/", views.cita_reprogramar, name="cita_reprogramar"),

    # Fichas
    path("fichas/", views.fichas_list, name="fichas_list"),
    path("fichas/nueva/", views.ficha_new, name="ficha_new"),
    path("fichas/<int:ficha_id>/", views.ficha_detail, name="ficha_detail"),
    path("fichas/<int:ficha_id>/publicacion/", views.ficha_toggle_publicacion, name="ficha_toggle_publicacion"),
    path("fichas/<int:ficha_id>/descargar/<int:adj_id>/", views.ficha_descargar_adjunto, name="ficha_descargar_adjunto"),

    # Reportes
    path("reportes/", views.reportes, name="reportes"),
]
