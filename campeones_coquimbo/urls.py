from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("core/", include(("applications.core.urls", "core"), namespace="core")),
    path("atleta/", include(("applications.atleta.urls", "atleta"), namespace="atleta")),
    path("usuarios/", include(("applications.usuarios.urls", "usuarios"), namespace="usuarios")),
    path("evaluaciones/", include(("applications.evaluaciones.urls", "evaluaciones"), namespace="evaluaciones")),
    path("pmul/", include(("applications.pmul.urls", "pmul"), namespace="pmul")),
    path("apoderado/", include(("applications.apoderado.urls", "apoderado"), namespace="apoderado")),
    path("profesor/", include(("applications.profesor.urls", "profesor"), namespace="profesor")),

    # raíz -> core:home
    path("", RedirectView.as_view(pattern_name="core:home", permanent=False)),

    path("cuenta/cambiar-clave/",
        RedirectView.as_view(pattern_name="usuarios:cambiar_password", permanent=False),
        name="cambiar_password",
         ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
