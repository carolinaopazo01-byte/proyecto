from django.urls import path
from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.login_rut, name="login_rut"),
    path("logout/", views.logout_view, name="logout"),

    # Paneles por rol
    path("panel/admin/", views.panel_admin, name="panel_admin"),
    path("panel/coordinador/", views.panel_coordinador, name="panel_coordinador"),
    path("panel/profesor/", views.panel_profesor, name="panel_profesor"),
    path("panel/apoderado/", views.panel_apoderado, name="panel_apoderado"),
    path("panel/profesional/", views.panel_prof_multidisciplinario, name="panel_prof_multidisciplinario"),
    path("panel/atleta/", views.panel_atleta, name="panel_atleta"),
]
