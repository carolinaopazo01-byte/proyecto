# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import Usuario, normalizar_rut


def _redirigir_por_tipo(user: Usuario):
    """
    Envía al panel según el tipo_usuario del modelo personalizado Usuario.
    """
    tipo = user.tipo_usuario
    if tipo == Usuario.Tipo.ADMIN:
        return redirect("usuarios:panel_admin")
    elif tipo == Usuario.Tipo.COORD:
        return redirect("usuarios:panel_coordinador")
    elif tipo == Usuario.Tipo.PROF:
        return redirect("usuarios:panel_profesor")
    elif tipo == Usuario.Tipo.APOD:
        return redirect("usuarios:panel_apoderado")
    elif tipo == Usuario.Tipo.PROF_MULT:
        return redirect("usuarios:panel_prof_multidisciplinario")
    return redirect("usuarios:panel_atleta")


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

@login_required
def panel_admin(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Administrador"})

@login_required
def panel_coordinador(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Coordinador"})

@login_required
def panel_profesor(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Profesor/Entrenador"})

@login_required
def panel_apoderado(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Apoderado"})

@login_required
def panel_prof_multidisciplinario(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Profesional Multidisciplinario"})

@login_required
def panel_atleta(request):
    return render(request, "usuarios/panel.html", {"titulo": "Panel Atleta"})
