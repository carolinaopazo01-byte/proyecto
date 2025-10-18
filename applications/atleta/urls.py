# applications/atleta/urls.py
from django.urls import path
from . import views

app_name = "atleta"

urlpatterns = [
    path("agenda/", views.agenda_disponible, name="agenda_disponible"),
    path("citas/nueva/", views.cita_crear, name="cita_crear"),
    path("proceso/ingreso-ar/", views.proceso_ingreso_alto_rendimiento, name="proceso_ingreso_ar"),
]
