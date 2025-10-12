from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.urls import reverse

@require_http_methods(["GET", "POST"])
def login_rut(request):
    # Solo demostración: no autenticamos aún.
    if request.method == "POST":
        # podrías leer request.POST["rut"] y ["password"] si quieres validar
        return redirect(reverse("usuarios:bienvenido"))
    return render(request, "usuarios/login.html")

@require_http_methods(["GET"])
def bienvenido(request):
    return render(request, "usuarios/bienvenido.html", {"next_url": reverse("core:estudiantes_list")})