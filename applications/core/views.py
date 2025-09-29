from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Sede, Deporte

def home(request):
    # Landing simple, en blanco (luego la “embellecemos”)
    return render(request, 'core/home.html')

@login_required
def sede_list(request):
    sedes = Sede.objects.all().order_by('nombre')
    return render(request, 'core/sede_list.html', {'sedes': sedes})

@login_required
def deporte_list(request):
    deportes = Deporte.objects.all().order_by('nombre')
    return render(request, 'core/deporte_list.html', {'deportes': deportes})
