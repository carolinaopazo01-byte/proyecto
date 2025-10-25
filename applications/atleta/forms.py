from django import forms
from .models import AsistenciaAtleta

class AsistenciaFilaForm(forms.Form):
    atleta_id = forms.IntegerField(widget=forms.HiddenInput)
    presente = forms.BooleanField(required=False)
    justificada = forms.BooleanField(required=False)
    observaciones = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Obs."}))

class InvitadoForm(forms.ModelForm):
    class Meta:
        model = AsistenciaAtleta
        fields = ["invitado_nombre", "invitado_rut", "invitado_contacto"]
        widgets = {
            "invitado_nombre": forms.TextInput(attrs={"required": True}),
        }
