# applications/apoderado/urls.py
from django.urls import path
from . import views

app_name = "apoderado"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("alumno/<int:pk>/", views.alumno_detalle, name="alumno_detalle"),  # 👈 aquí
    path("asistencia/", views.asistencia, name="asistencia"),
    path("planificacion/", views.planificacion, name="planificacion"),
    path("evaluaciones/", views.evaluaciones, name="evaluaciones"),
    path("comunicados/", views.comunicados, name="comunicados"),
    path("protocolos/", views.protocolos, name="protocolos"),
]
