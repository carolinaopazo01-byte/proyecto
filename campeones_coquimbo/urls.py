from django.contrib import admin
from django.urls import path, include
from applications.core import views as core_views  # 👈 importamos el home

urlpatterns = [
    path('admin/', admin.site.urls),

    # Home (página en blanco)
    path('', core_views.home, name='home'),

    # Core bajo /core/...  (sedes, deportes, login de core)
    path('core/', include('applications.core.urls')),

    # Clases y asistencia
    path('', include('applications.atleta.urls')),

    # Evals/planificaciones
    path('evals/', include('applications.evaluaciones.urls')),

    # Login/Logout “oficial”
    path('cuentas/', include('applications.usuarios.urls')),
]
