from django.contrib import admin
from django.urls import path, include
from applications.core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('applications.core.urls')),

    # Asistencia
    path('asistencia/', core_views.asistencia, name='asistencia'),                        # sin curso seleccionado
    path('asistencia/<int:curso_id>/', core_views.asistencia, name='asistencia_curso'),   # con curso

    # Usuarios
    path('alumno/cursos/', core_views.alumno_cursos, name='alumno_cursos'),
    path('alumno/asistencia/', core_views.alumno_asistencia, name='alumno_asistencia'),
    path('alumno/comunicados/', core_views.comunicados_alumnos, name='comunicados_alumnos'),
    path('admin/cursos/', core_views.cursos_admin, name='cursos_admin'),
    path('dashboard/', core_views.dashboard, name='dashboard'),
    path('login/', core_views.login, name='login'),
    path('panel/alumno/', core_views.panel_alumno, name='panel_alumno'),
    path('reportes/', core_views.reportes, name='reportes'),

    # Core
    path('', core_views.home, name='home'),
    path('inicio/', core_views.inicio, name='inicio'),
    path('deportes/', core_views.deporte_list, name='deporte_list'),

    # Atleta
    path('clase/form/', core_views.clase_form, name='clase_form'),
    path('clase/list/', core_views.clase_list, name='clase_list'),

    # Evaluaciones
    path('evaluaciones/', core_views.evaluacion_list, name='evaluacion_list'),
    path('planificaciones/', core_views.planificacion_list, name='planificacion_list'),
]

