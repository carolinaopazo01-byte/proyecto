from django.urls import path
from .views import inicio, marcar_asistencia, alumno_cursos
from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"), # página principal
    path('asistencia/', marcar_asistencia, name='marcar_asistencia'),
    path('alumno/cursos/', alumno_cursos, name='alumno_cursos'),
    ]
