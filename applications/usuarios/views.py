# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import Usuario
from .utils import normalizar_rut  # <— AQUÍ ESTABA EL PROBLEMA

def _redirigir_por_tipo(user: Usuario):
    t = user.tipo_usuario
    if t == Usuario.Tipo.ADMIN:
        return redirect("usuarios:panel_admin")
    if t == Usuario.Tipo.COORD:
        return redirect("usuarios:panel_coordinador")
    if t == Usuario.Tipo.PROF:
        return redirect("usuarios:panel_profesor")
    if t == Usuario.Tipo.APOD:
        return redirect("usuarios:panel_apoderado")
    if t == Usuario.Tipo.PMUL:
        return redirect("usuarios:panel_prof_multidisciplinario")
    return redirect("usuarios:panel_atleta")

@require_http_methods(["GET", "POST"])
def login_rut(request):
    if request.method == "POST":
        rut = normalizar_rut(request.POST.get("rut") or "")
        password = request.POST.get("password") or ""
        user = authenticate(request, username=rut, password=password)
        if user:
            login(request, user)
            return _redirigir_por_tipo(user)
        return render(request, "usuarios/login.html", {"error": "RUT o contraseña incorrectos"})
    return render(request, "usuarios/login.html")

def logout_view(request):
    logout(request)
    return redirect("core:home")

# Stubs de paneles (ajusta con tus templates si ya los tienes)
def panel_admin(request):                return render(request, "usuarios/panel_admin.html")
def panel_coordinador(request):          return render(request, "usuarios/panel_coordinador.html")
def panel_profesor(request):             return render(request, "usuarios/panel_profesor.html")
def panel_apoderado(request):            return render(request, "usuarios/panel_apoderado.html")
def panel_prof_multidisciplinario(request): return render(request, "usuarios/panel_prof_multidisciplinario.html")
def panel_atleta(request):               return render(request, "usuarios/panel_atleta.html")
