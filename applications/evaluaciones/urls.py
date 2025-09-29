from django.urls import path
from . import views

urlpatterns = [
    path('planificaciones/', views.planificacion_list, name='planificacion_list'),
    path('evaluaciones/',   views.evaluacion_list,   name='evaluacion_list'),
]
