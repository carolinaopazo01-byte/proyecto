# applications/atleta/urls.py
from django.urls import path
from .views import panel_atleta
from . import views

app_name = "atleta"

urlpatterns = [
    path("panel/", views.panel_atleta, name="panel"),
    path("agenda/", views.agenda_disponible, name="agenda_disponible"),
    path("citas/nueva/", views.cita_crear, name="cita_crear"),
    path("proceso/ingreso-ar/", views.proceso_ingreso_alto_rendimiento,
         name="proceso_ingreso_ar"),

  # Panel del profesor
    path("prof/panel/", views.prof_panel, name="prof_panel"),    # Lista de clases del profesor
    path("prof/clases/", views.prof_clases, name="prof_clases"),    # Tomar asistencia de una clase
    path("prof/clase/<int:clase_id>/asistencia/", views.prof_tomar_asistencia, name="prof_tomar_asistencia"),   # Acciones auxiliares
    path("prof/clase/<int:clase_id>/levantar-cupo/<int:atleta_id>/", views.prof_levantar_cupo, name="prof_levantar_cupo"),
    path("prof/clase/<int:clase_id>/invitado/", views.prof_agregar_invitado, name="prof_agregar_invitado"),
]

