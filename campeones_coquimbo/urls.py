from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('applications.atleta.urls')),         # home y asistencia
    path('core/', include('applications.core.urls')),      # sedes/deportes
    path('evals/', include('applications.evaluaciones.urls')),  # planificaciones/evaluaciones
    path('cuentas/', include('applications.usuarios.urls')),    # login/logout
]