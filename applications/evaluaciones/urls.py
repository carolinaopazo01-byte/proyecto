from django.urls import path
from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("<int:estudiante_id>/", views.evaluaciones_list, name="evaluaciones_list"),
    path("<int:estudiante_id>/nueva/", views.evaluacion_create, name="evaluacion_create"),
]
