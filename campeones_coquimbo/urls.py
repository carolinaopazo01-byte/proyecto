from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),


    path("core/", include("applications.core.urls")),
    path("atleta/", include("applications.atleta.urls")),
    path("usuarios/", include("applications.usuarios.urls")),
    path("evaluaciones/", include("applications.evaluaciones.urls")),
    path("pmul/", include("applications.pmul.urls")),
    path("apoderado/", include("applications.apoderado.urls")),
    path("profesor/", include("applications.profesor.urls")),


    path("", RedirectView.as_view(pattern_name="core:home", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
