from django.contrib import admin
from django.urls import path
from applications.atleta import views as atleta_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', atleta_views.dashboard, name='dashboard'),
    path('clase/<int:pk>/asistencia/', atleta_views.marcar_asistencia, name='marcar_asistencia'),
]
