from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("applications.core.urls", namespace="core")),
    path("atleta/", include("applications.atleta.urls", namespace="atleta")),
    path("usuarios/", include("applications.usuarios.urls", namespace="usuarios")),
    path("evaluaciones/", include("applications.evaluaciones.urls", namespace="evaluaciones")),
]
