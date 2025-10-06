from django.shortcuts import render

def inicio(request):
    # Ejemplo: pasar datos al template
    contexto = {"nombre_pagina": "Inicio", "mensaje": "¡Hola, Carolina!"}
    return render(request, "core/home.html", contexto)

def acerca(request):
    contexto = {"nombre_pagina": "Acerca de"}
    return render(request, "core/acerca.html", contexto)
