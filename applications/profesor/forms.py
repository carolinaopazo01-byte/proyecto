from django import forms
from applications.core.models import Estudiante

class AlumnoTemporalForm(forms.ModelForm):
    motivacion_beca = forms.CharField(
        required=False,
        label="Motivación del deportista para postular a la beca",
        widget=forms.Textarea(attrs={"rows": 3})
    )

    class Meta:
        model = Estudiante
        fields = [
            "nombres", "apellidos", "fecha_nacimiento", "rut",
            "direccion", "comuna", "telefono", "email",
            "n_emergencia", "prevision",
            "apoderado_nombre", "apoderado_telefono",
            "apoderado_email", "apoderado_fecha_nacimiento",
            "curso",
        ]
        labels = {
            "n_emergencia": "Número de emergencia",
            "apoderado_nombre": "Nombre completo (tutor/a)",
            "apoderado_telefono": "Teléfono (tutor/a)",
            "apoderado_email": "Correo electrónico (tutor/a)",
            "apoderado_fecha_nacimiento": "Fecha de nacimiento (tutor/a)",
            "curso": "Curso y sede al cual postula",
        }
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "apoderado_fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
