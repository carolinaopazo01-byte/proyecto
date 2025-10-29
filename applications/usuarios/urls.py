# applications/usuarios/urls.py
from django.urls import path
from . import views  # , views_equipo, views_admin
from django.contrib.auth import views as auth_views

app_name = "usuarios"

urlpatterns = [
    # Login / Logout
    path("login/", views.login_rut, name="login_rut"),
    path("logout/", views.logout_view, name="logout"),

    # Paneles por rol (coinciden con tus vistas reales)
    path("panel/admin/", views.panel_admin, name="panel_admin"),
    path("panel/coordinador/", views.panel_coordinador, name="panel_coordinador"),
    path("panel/profesor/", views.panel_profesor, name="panel_profesor"),
    path("panel/apoderado/", views.panel_apoderado, name="panel_apoderado"),
    path("panel/profesional/", views.panel_prof_multidisciplinario, name="panel_prof_multidisciplinario"),
    path("panel/atleta/", views.panel_atleta, name="panel_atleta"),



    # Recuperar contraseña (password reset)
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="usuarios/password_reset.html"
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="usuarios/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="usuarios/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="usuarios/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # Equipo (CRUD) - nombres “nuevos”
    path("equipo/", views.usuarios_list, name="usuarios_list"),
    path("equipo/nuevo/", views.usuario_create, name="usuario_create"),
    path("equipo/<int:usuario_id>/", views.usuario_detail, name="usuario_detail"),
    path("equipo/<int:usuario_id>/editar/", views.usuario_edit, name="usuario_edit"),
    path("equipo/<int:usuario_id>/toggle/", views.usuario_toggle_active, name="usuario_toggle_active"),
    path("equipo/<int:usuario_id>/eliminar/", views.usuario_delete, name="usuario_delete"),

    # Aliases para plantillas antiguas (se mantienen, mismos paths con otros names)
    path("equipo/nuevo/", views.usuario_create, name="equipo_new"),
    path("equipo/", views.usuarios_list, name="equipo_list"),
    path("equipo/<int:usuario_id>/editar/", views.usuario_edit, name="equipo_edit"),
    path("equipo/<int:usuario_id>/eliminar/", views.usuario_delete, name="equipo_delete"),
    path("equipo/<int:usuario_id>/toggle/", views.usuario_toggle_active, name="equipo_toggle"),
    path("equipo/<int:usuario_id>/", views.usuario_detail, name="equipo_view"),
]
