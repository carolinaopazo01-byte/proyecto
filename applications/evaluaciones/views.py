from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Planificacion, Evaluacion

@login_required
def planificacion_list(request):
    planes = Planificacion.objects.select_related('profesor').order_by('-mes')
    return render(request, 'evaluaciones/planificacion_list.html', {'planes': planes})

@login_required
def evaluacion_list(request):
    evals = Evaluacion.objects.select_related('atleta','profesional').order_by('-fecha')
    return render(request, 'evaluaciones/evaluacion_list.html', {'evals': evals})
