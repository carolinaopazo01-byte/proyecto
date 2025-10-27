# applications/usuarios/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import views_profesor  # importa las vistas del panel profesor

app_name = "usuarios"

urlpatterns = [
    # Auth
    path("login/", views.login_rut, name="login_rut"),
    path("logout/", views.logout_view, name="logout"),

    # Panel general (usa tu función existente panel_view)
    path("panel/", views.panel_view, name="panel"),

    # Paneles por rol
    path("panel/admin/", views.panel_admin, name="panel_admin"),
    path("panel/coordinador/", views.panel_coordinador, name="panel_coordinador"),
    path("panel/apoderado/", views.panel_apoderado, name="panel_apoderado"),
    path("panel/profesional/", views.panel_prof_multidisciplinario, name="panel_prof_multidisciplinario"),
    path("panel/atleta/", views.panel_atleta, name="panel_atleta"),

    # Profesor / Entrenador
    path("panel/profesor/", views_profesor.panel_profesor, name="panel_profesor"),
    path("profesor/cursos/", views_profesor.mis_cursos, name="mis_cursos_prof"),
    path("profesor/asistencia/", views_profesor.asistencia_listado, name="asistencia_profesor"),
    path("profesor/asistencia/<int:curso_id>/", views_profesor.asistencia_tomar, name="asistencia_tomar"),
    path("profesor/planificaciones/", views_profesor.planificaciones, name="planificaciones_prof"),
    path("profesor/comunicados/", views_profesor.comunicados, name="comunicados_prof"),
    path("profesor/perfil/", views_profesor.mi_perfil, name="perfil_profesor"),

    # Recuperar contraseña
    path("password_reset/", auth_views.PasswordResetView.as_view(
        template_name="usuarios/password_reset.html"
    ), name="password_reset"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="usuarios/password_reset_done.html"
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="usuarios/password_reset_confirm.html"
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="usuarios/password_reset_complete.html"
    ), name="password_reset_complete"),

    # Equipo (CRUD) — si los usas, déjalos
    path("equipo/", views.usuarios_list, name="usuarios_list"),
    path("equipo/nuevo/", views.usuario_create, name="usuario_create"),
    path("equipo/<int:usuario_id>/", views.usuario_detail, name="usuario_detail"),
    path("equipo/<int:usuario_id>/editar/", views.usuario_edit, name="usuario_edit"),
    path("equipo/<int:usuario_id>/toggle/", views.usuario_toggle_active, name="usuario_toggle_active"),
    path("equipo/<int:usuario_id>/eliminar/", views.usuario_delete, name="usuario_delete"),

    # Aliases heredados (opcional)
    path("equipo/nuevo/", views.usuario_create, name="equipo_new"),
    path("equipo/", views.usuarios_list, name="equipo_list"),
    path("equipo/<int:usuario_id>/editar/", views.usuario_edit, name="equipo_edit"),
    path("equipo/<int:usuario_id>/eliminar/", views.usuario_delete, name="equipo_delete"),
    path("equipo/<int:usuario_id>/toggle/", views.usuario_toggle_active, name="equipo_toggle"),
    path("equipo/<int:usuario_id>/", views.usuario_detail, name="equipo_view"),
]
