# applications/core/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Sede, Estudiante
from applications.usuarios.models import normalizar_rut

# --- Sede ---
class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ["nombre", "direccion", "descripcion", "capacidad"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "capacidad": forms.NumberInput(attrs={"min": 0}),
        }

# --- Curso ---
# Si ya tienes CursoForm definido en otro momento, puedes conservarlo.
# Lo dejo como placeholder simple por si no existía:
# from .models import Curso
# class CursoForm(forms.ModelForm):
#     class Meta:
#         model = Curso
#         fields = "__all__"

# ====== utilidades RUT (validación y formato) ======
def _rut_calc_dv(numero: str) -> str:
    factores = [2, 3, 4, 5, 6, 7]
    s, i = 0, 0
    for d in reversed(numero):
        s += int(d) * factores[i]
        i = (i + 1) % len(factores)
    r = 11 - (s % 11)
    if r == 11: return "0"
    if r == 10: return "K"
    return str(r)

def _rut_formatea(ch: str) -> str:
    base = "".join([c for c in ch if c.isdigit()])
    dv   = ch[-1].upper()
    partes = []
    while len(base) > 3:
        partes.insert(0, base[-3:])
        base = base[:-3]
    if base:
        partes.insert(0, base)
    return ".".join(partes) + "-" + dv

# --- Estudiante ---
class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "rut", "nombres", "apellidos", "fecha_nacimiento",
            "email", "telefono",
            "apoderado_nombre", "apoderado_telefono",
            "curso", "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "rut": "RUT",
            "apoderado_nombre": "Nombre apoderado",
            "apoderado_telefono": "Teléfono apoderado",
        }

    def clean_rut(self):
        rut = (self.cleaned_data.get("rut") or "").strip()
        if not rut:
            raise ValidationError("Debes ingresar el RUT.")

        rut_norm = normalizar_rut(rut)  # -> '########-DV'
        try:
            base, dv = rut_norm.split("-")
        except ValueError:
            raise ValidationError("RUT inválido.")

        if not base.isdigit() or len(base) < 6:
            raise ValidationError("RUT inválido.")

        dv_calc = _rut_calc_dv(base)
        if dv.upper() != dv_calc:
            raise ValidationError("Dígito verificador incorrecto.")

        # Unicidad real ignorando formato
        qs = Estudiante.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for e in qs:
            from_db = normalizar_rut(e.rut)
            if from_db.upper() == rut_norm.upper():
                raise ValidationError("Ya existe un estudiante con ese RUT.")

        return _rut_formatea(base + dv.upper())

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.rut = self.cleaned_data["rut"]
        if commit:
            obj.save()
            self.save_m2m()
        return obj
