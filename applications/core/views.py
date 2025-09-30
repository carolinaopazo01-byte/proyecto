# applications/core/views.py
from django.shortcuts import render


def inicio(request):
    return render(request, "core/inicio.html")

def marcar_asistencia(request):
    return render(request, "core/marcar_asistencia.html")
from django.shortcuts import render

def asistencia(request):
    return render(request, "core/marcar_asistencia.html")


from django.shortcuts import render

# --- Vistas de usuarios ---
def alumno_cursos(request):
    return render(request, "usuarios/alumno_cursos.html")

def alumno_asistencia(request):
    return render(request, "usuarios/alumno_asistencia.html")

def comunicados_alumnos(request):
    return render(request, "usuarios/comunicados_alumnos.html")

def cursos_admin(request):
    return render(request, "usuarios/cursos_admin.html")

def dashboard(request):
    return render(request, "usuarios/dashboard.html")

def login(request):
    return render(request, "usuarios/login.html")

def panel_alumno(request):
    return render(request, "usuarios/panel_alumno.html")

def reportes(request):
    return render(request, "usuarios/reportes.html")

# --- Vistas de core ---
def home(request):
    return render(request, "core/home.html")

def inicio(request):
    return render(request, "core/inicio.html")

def deporte_list(request):
    return render(request, "core/deporte_list.html")

# --- Vistas de atleta ---
def clase_form(request):
    return render(request, "atleta/clase_form.html")

def clase_list(request):
    return render(request, "atleta/clase_list.html")

# --- Vistas de evaluaciones ---
def evaluacion_list(request):
    return render(request, "evaluaciones/evaluacion_list.html")

def planificacion_list(request):
    return render(request, "evaluaciones/planificacion_list.html")
