from django.urls import path
from . import views

urlpatterns = [
    path('clases/', views.dashboard, name='dashboard'),
    path('clases/listado/', views.clase_list, name='clase_list'),
    path('clase/nueva/', views.clase_create, name='clase_create'),
    path('clase/<int:pk>/asistencia/', views.marcar_asistencia, name='marcar_asistencia'),
]
