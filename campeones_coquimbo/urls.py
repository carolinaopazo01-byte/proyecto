from django.contrib import admin
from django.urls import path, include
from applications.core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('applications.core.urls')),
    path('asistencia/', core_views.asistencia, name='asistencia'),                    # sin curso seleccionado
    path('asistencia/<int:curso_id>/', core_views.asistencia, name='asistencia_curso'),  # con curso
]
