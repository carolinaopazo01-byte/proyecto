from django import forms
from applications.core.models import Curso
from applications.usuarios.models import Usuario

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nombre", "programa", "disciplina", "categoria",
            "profesor", "horario", "sede", "cupos",
            "publicado", "lista_espera"
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "programa": forms.Select(attrs={"class": "form-select"}),
            "disciplina": forms.Select(attrs={"class": "form-select"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "profesor": forms.Select(attrs={"class": "form-select"}),
            "horario": forms.TextInput(attrs={"class": "form-control"}),
            "sede": forms.Select(attrs={"class": "form-select"}),
            "cupos": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # solo profesores en el combo
        self.fields["profesor"].queryset = Usuario.objects.filter(tipo_usuario=Usuario.Tipo.PROF)

    def clean_cupos(self):
        v = self.cleaned_data["cupos"]
        if v <= 0:
            raise forms.ValidationError("Los cupos deben ser mayores a 0.")
        return v
