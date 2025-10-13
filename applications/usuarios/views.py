# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

# Control de acceso por rol
from applications.usuarios.utils import role_required
from applications.usuarios.models import Usuario

from .models import Usuario, normalizar_rut

def _redirigir_por_tipo(user: Usuario):
    """
    Envía automáticamente al área principal según el tipo_usuario.
    """
    tipo = user.tipo_usuario

    if tipo == Usuario.Tipo.ADMIN:
        # Acceso total: panel de control
        return redirect("usuarios:panel_admin")

    elif tipo == Usuario.Tipo.COORD:
        # Supervisión de cursos y planificación
        return redirect("core:cursos_list")

    elif tipo == Usuario.Tipo.PROF:
        # Profesores inician en planificación
        return redirect("core:planificacion_upload")

    elif tipo == Usuario.Tipo.PROF_MULT:
        # Equipo multidisciplinario va directo a su agenda
        return redirect("atleta:agenda_disponible")

    elif tipo == Usuario.Tipo.APOD:
        # Apoderados ven comunicados por defecto
        return redirect("core:comunicados_list")

    elif tipo == Usuario.Tipo.ATLE:
        # Atletas (AR o Formativo) revisan agenda
        return redirect("atleta:agenda_disponible")

    # En caso de tipo desconocido
    return redirect("core:home")

@require_http_methods(["GET", "POST"])
def login_rut(request):
    """
    Login por RUT + contraseña usando RutBackend (rut en username).
    """
    if request.method == "POST":
        rut = normalizar_rut(request.POST.get("rut"))
        password = request.POST.get("password")
        user = authenticate(request, username=rut, password=password)
        if user:
            login(request, user)
            return _redirigir_por_tipo(user)
        return render(request, "usuarios/login.html", {"error": "RUT o contraseña incorrectos"})
    return render(request, "usuarios/login.html")


def logout_view(request):
    """
    Cierra sesión y vuelve al Home.
    """
    logout(request)
    return redirect("core:home")


# ----------------- PANELES POR ROL -----------------

@role_required(Usuario.Tipo.ADMIN)
def panel_admin(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Administrador"})

@role_required(Usuario.Tipo.COORD)
def panel_coordinador(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Coordinador"})

@role_required(Usuario.Tipo.PROF)
def panel_profesor(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Profesor/Entrenador"})

@role_required(Usuario.Tipo.APOD)
def panel_apoderado(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Apoderado"})

@role_required(Usuario.Tipo.PROF_MULT)
def panel_prof_multidisciplinario(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Profesional Multidisciplinario"})

@role_required(Usuario.Tipo.ATLE)
def panel_atleta(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Atleta"})
