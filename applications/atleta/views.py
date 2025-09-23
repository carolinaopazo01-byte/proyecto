from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.forms import modelformset_factory
from .models import Clase, AsistenciaAtleta

def dashboard(request):
    clases = Clase.objects.order_by('fecha','hora_inicio')[:20]
    return render(request, 'dashboard.html', {'clases': clases})

def marcar_asistencia(request, pk):
    clase = get_object_or_404(Clase, pk=pk)
    AsistenciaFormSet = modelformset_factory(
        AsistenciaAtleta,
        fields=('presente','observaciones'),
        extra=0
    )
    qs = AsistenciaAtleta.objects.filter(clase=clase).select_related('atleta')
    if request.method == 'POST':
        formset = AsistenciaFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Asistencia guardada.')
            return redirect('dashboard')
    else:
        formset = AsistenciaFormSet(queryset=qs)
    return render(request, 'marcar_asistencia.html', {'clase': clase, 'formset': formset})
