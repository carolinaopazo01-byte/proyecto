from django.shortcuts import render

def marcar_asistencia(request):
    return render(request, "core/marcar_asistencia.html")
