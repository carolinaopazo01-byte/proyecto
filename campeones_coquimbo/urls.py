from django.contrib import admin
from django.urls import path, include
from django.conf import settings              # ← IMPORTANTE
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("applications.core.urls", namespace="core")),
    path("atleta/", include("applications.atleta.urls", namespace="atleta")),
    path("usuarios/", include("applications.usuarios.urls", namespace="usuarios")),
    path("evaluaciones/", include("applications.evaluaciones.urls", namespace="evaluaciones")),
    path("pmul/", include("applications.pmul.urls", namespace="pmul")),
    path("apoderado/", include("applications.apoderado.urls", namespace="apoderado")),
    path("profesor/", include("applications.profesor.urls", namespace="profesor")),

path("", RedirectView.as_view(pattern_name="core:home", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)