from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import modelform_factory, modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from .models import Clase, AsistenciaAtleta

@login_required
def dashboard(request):
    clases = Clase.objects.order_by('fecha','hora_inicio')[:20]
    return render(request, 'dashboard.html', {'clases': clases})

@login_required
def clase_list(request):
    clases = Clase.objects.select_related('sede_deporte','profesor').order_by('-fecha')
    return render(request, 'atleta/clase_list.html', {'clases': clases})

@login_required
def clase_create(request):
    ClaseForm = modelform_factory(Clase, fields=('sede_deporte','profesor','fecha','hora_inicio','hora_fin','tema','descripcion'))
    if request.method == 'POST':
        form = ClaseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Clase creada.')
            return redirect('clase_list')
    else:
        form = ClaseForm()
    return render(request, 'atleta/clase_form.html', {'form': form})

@login_required
def marcar_asistencia(request, pk):
    clase = get_object_or_404(Clase, pk=pk)
    AsistenciaFormSet = modelformset_factory(AsistenciaAtleta, fields=('presente','observaciones'), extra=0)
    qs = AsistenciaAtleta.objects.filter(clase=clase).select_related('atleta','clase')
    if request.method == 'POST':
        formset = AsistenciaFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Asistencia guardada.')
            return redirect('dashboard')
    else:
        formset = AsistenciaFormSet(queryset=qs)
    return render(request, 'marcar_asistencia.html', {'clase': clase, 'formset': formset})
