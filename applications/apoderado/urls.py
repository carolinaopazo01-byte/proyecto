# applications/apoderado/urls.py
from django.urls import path
from . import views

app_name = "apoderado"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # TODAS sin pk: las vistas resuelven el alumno por request.user
    path("alumno/", views.alumno_detalle, name="alumno_detalle"),
    path("asistencia/", views.asistencia, name="asistencia"),
    path("evaluaciones/", views.evaluaciones, name="evaluaciones"),
    path("planificacion/", views.planificacion, name="planificacion"),
    path("protocolos/", views.protocolos, name="protocolos"),

]
