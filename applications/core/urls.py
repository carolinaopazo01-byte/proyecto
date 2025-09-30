from django.urls import path
from .views import inicio, marcar_asistencia

urlpatterns = [
    path('', inicio, name='inicio'),   # página principal
    path('asistencia/', marcar_asistencia, name='marcar_asistencia'),
]
