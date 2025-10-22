from django import forms
from django.utils import timezone

from applications.core.models import Estudiante  # ajusta si tu "paciente" tiene otro nombre
from .models import Cita, FichaClinica, FichaAdjunto

# ----------------- CITA (Form puro, no ModelForm) -----------------
class CitaForm(forms.Form):
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    hora_inicio = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    hora_fin = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))

    paciente = forms.ModelChoiceField(queryset=Estudiante.objects.all())
    observacion = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    estado = forms.ChoiceField(choices=Cita.ESTADOS, initial="PEND")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)  # profesional logueado
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        f = cleaned.get("fecha")
        hi = cleaned.get("hora_inicio")
        hf = cleaned.get("hora_fin")

        # Combinar fecha + horas a datetimes conscientes de zona
        if f and hi:
            cleaned["inicio_dt"] = timezone.make_aware(timezone.datetime.combine(f, hi))
        if f and hf:
            cleaned["fin_dt"] = timezone.make_aware(timezone.datetime.combine(f, hf))
        return cleaned

    def save(self):
        """
        Creamos la Cita manualmente para no depender de nombres de campos
        en un ModelForm al momento del import.
        """
        cd = self.cleaned_data
        inicio = cd.get("inicio_dt")
        fin = cd.get("fin_dt")
        instancia = Cita.objects.create(
            paciente=cd["paciente"],
            profesional=self.user,
            inicio=inicio,
            fin=fin,
            observacion=cd.get("observacion", ""),
            estado=cd.get("estado", "PEND"),
        )
        return instancia


# ----------------- FICHAS (Sí usamos ModelForm) -----------------
class FichaClinicaForm(forms.ModelForm):
    class Meta:
        model = FichaClinica
        fields = [
            "paciente",
            "motivo",
            "observaciones",
            "diagnostico",
            "estado",
            "publicar_profesor",
            "publicar_coordinador",
            "publicar_admin",
        ]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 5}),
            "diagnostico": forms.Textarea(attrs={"rows": 4}),
        }

class AdjuntoForm(forms.ModelForm):
    class Meta:
        model = FichaAdjunto
        fields = ["archivo", "nombre"]
