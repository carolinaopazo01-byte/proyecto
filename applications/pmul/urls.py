from django.urls import path
from . import views
from . import views_disponibilidad as d

app_name = "pmul"

urlpatterns = [

    path("slots/", d.mis_slots, name="slots_list"),                      # listado
    path("slots/nuevo/", d.slot_nuevo, name="slot_nuevo"),              # formulario manual
    path("slots/lote/nuevo/", d.slots_bulk_new, name="slots_bulk_new"),  # generación automática
    path("slots/<int:slot_id>/cancelar/", d.slot_cancelar, name="slot_cancelar"),
path("slots/<int:slot_id>/editar/", d.slot_editar, name="slot_editar"),



    path("reservar/", d.reservar_listado, name="reservar_listado"),
    path("reservar/<int:slot_id>/", d.reservar_confirmar, name="reservar_confirmar"),


    path("", views.panel, name="panel"),
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/nueva/", views.cita_new, name="cita_new"),
    path("agenda/<int:cita_id>/editar/", views.cita_edit, name="cita_edit"),
    path("agenda/<int:cita_id>/cancelar/", views.cita_cancel, name="cita_cancel"),
    path("agenda/<int:cita_id>/reprogramar/", views.cita_reprogramar, name="cita_reprogramar"),

    path("fichas/", views.fichas_list, name="fichas_list"),
    path("fichas/nueva/", views.ficha_new, name="ficha_new"),
    path("fichas/<int:ficha_id>/", views.ficha_detail, name="ficha_detail"),
    path("fichas/<int:ficha_id>/publicacion/", views.ficha_toggle_publicacion, name="ficha_toggle_publicacion"),
    path("fichas/<int:ficha_id>/descargar/<int:adj_id>/", views.ficha_descargar_adjunto, name="ficha_descargar_adjunto"),

    path("reportes/", views.reportes, name="reportes"),
]
