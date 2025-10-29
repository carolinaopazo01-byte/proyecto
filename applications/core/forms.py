# applications/core/forms.py
from datetime import date, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db import models  # <-- necesario para models.Q
from django.db.models import Q

from .models import Sede, Comunicado

from .models import (
    Sede,
    Estudiante,
    Curso,
    Planificacion,
    Deporte,
    CursoHorario,
)


# =========================================================
#                       PLANIFICACIÓN
# =========================================================
MAX_MB = 10
ALLOWED_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}

def _monday(d):
    return d - timedelta(days=d.weekday())

class PlanificacionUploadForm(forms.ModelForm):
    semana = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Semana (elige cualquier día de la semana; se ajustará al lunes)"
    )
    # archivo OPCIONAL
    archivo = forms.FileField(
        required=False,
        label="Archivo (PDF / DOCX / XLS / XLSX, máx. 10 MB)",
        help_text="Opcional: puedes guardar sin subir archivo",
    )

    class Meta:
        model = Planificacion
        fields = ["curso", "semana", "archivo", "comentarios", "publica"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        qs = Curso.objects.select_related("sede", "disciplina", "profesor") \
                          .order_by("sede__nombre", "disciplina__nombre", "nombre")
        if user and getattr(user, "tipo_usuario", "") == "PROF":
            qs = qs.filter(models.Q(profesor=user) | models.Q(profesores_apoyo=user)).distinct()
        self.fields["curso"].queryset = qs

        if not self.initial.get("semana"):
            self.initial["semana"] = timezone.localdate()

    # ✅ Maneja archivo opcional
    def clean_archivo(self):
        f = self.cleaned_data.get("archivo")
        if not f:
            return None
        if getattr(f, "size", 0) > MAX_MB * 1024 * 1024:
            raise ValidationError(f"El archivo supera {MAX_MB} MB.")
        name = f.name.lower()
        if not any(name.endswith(ext) for ext in ALLOWED_EXTS):
            raise ValidationError("Formato no permitido. Use PDF/DOC/DOCX/XLS/XLSX.")
        return f

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("semana"):
            cleaned["semana"] = _monday(cleaned["semana"])
            self.cleaned_data["semana"] = cleaned["semana"]
        return cleaned
# =========================================================
#                   HELPERS RUT (top-level)
# =========================================================
def _rut_normaliza(rut: str) -> str:
    """
    '12.345.678-9' -> '12345678-9'
    '123456789'    -> '12345678-9'
    """
    if not rut:
        return ""
    r = (
        rut.strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("–", "-")
        .replace("—", "-")
        .upper()
    )
    if "-" not in r and len(r) >= 2:
        r = r[:-1] + "-" + r[-1]
    if "-" in r:
        base, dv = r.split("-", 1)
        r = f"{base}-{dv.upper()}"
    return r


def _rut_calc_dv(base: str) -> str:
    """Calcula el DV chileno (módulo 11). `base` sólo dígitos."""
    suma, mult = 0, 2
    for d in reversed(base):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def _rut_igual(a: str, b: str) -> bool:
    return _rut_normaliza(a) == _rut_normaliza(b)


# =========================================================
#                            SEDES
# =========================================================

class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ["nombre", "comuna", "direccion",
                  "latitud", "longitud", "radio_metros",
                  "capacidad", "activa", "descripcion"]
        widgets = {
            "latitud": forms.HiddenInput(),
            "longitud": forms.HiddenInput(),
        }
        labels = {
            "radio_metros": "Radio de validación (m)",
        }

# =========================================================
#                           CURSOS
# =========================================================
class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            # 1) Identificación
            "nombre",
            "programa",
            "disciplina",
            "categoria",
            "sede",
            # 2) Calendario
            "fecha_inicio",
            "fecha_termino",
            # 3) Profesorado
            "profesor",
            "profesores_apoyo",
            # 4) Cupos e inscripciones
            "cupos",
            "cupos_espera",
            "permitir_inscripcion_rapida",
            # 5) Visibilidad/Estado
            "publicado",
            "estado",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_termino": forms.DateInput(attrs={"type": "date"}),
            "profesores_apoyo": forms.SelectMultiple(attrs={"size": 6}),
        }
        labels = {
            "disciplina": "Disciplina",
            "categoria": "Categoría (Sub-12, Adulto, Mixto)",
            "sede": "Sede/Recinto",
        }


class CursoHorarioForm(forms.ModelForm):
    class Meta:
        model = CursoHorario
        fields = ["dia", "hora_inicio", "hora_fin"]
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }


CursoHorarioFormSet = inlineformset_factory(
    parent_model=Curso,
    model=CursoHorario,
    form=CursoHorarioForm,
    extra=1,
    can_delete=True,
)


# =========================================================
#                         ESTUDIANTE
# =========================================================
class EstudianteForm(forms.ModelForm):
    # Marcador que NO se guarda en BD (sólo en el form)
    sin_info_deportiva = forms.BooleanField(
        required=False,
        label="No tiene información deportiva aún",
        help_text="Si lo marcas, se guardará sin información deportiva.",
    )

    class Meta:
        model = Estudiante
        fields = [
            # 1) Identificación del/la atleta
            "rut",
            "nombres",
            "apellidos",
            "fecha_nacimiento",
            "direccion",
            "comuna",
            "telefono",
            "email",
            # 2) Tutor (si es menor de edad)
            "apoderado_nombre",
            "apoderado_telefono",
            "apoderado_rut",
            # 3) Información deportiva (toda opcional)
            "pertenece_organizacion",
            "club_nombre",
            "logro_nacional",
            "logro_internacional",
            "categoria_competida",
            "puntaje_o_logro",
            # Otros
            "curso",
            "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "rut": "RUT",
            "direccion": "Dirección",
            "comuna": "Comuna",
            "telefono": "Teléfono",
            "email": "Email",
            "apoderado_nombre": "Nombre apoderado",
            "apoderado_telefono": "Teléfono apoderado",
            "pertenece_organizacion": "¿Pertenece a una organización deportiva?",
            "club_nombre": "Nombre del club",
            "logro_nacional": "Logro nacional",
            "logro_internacional": "Logro internacional",
            "categoria_competida": "Categoría en la cual compitió",
            "puntaje_o_logro": "Puntaje o logro obtenido",
        }

    # ---------- RUT ----------
    def clean_rut(self):
        rut = (self.cleaned_data.get("rut") or "").strip()
        if not rut:
            raise ValidationError("Debes ingresar el RUT.")

        rut_norm = _rut_normaliza(rut)  # '########-DV'
        try:
            base, dv = rut_norm.split("-")
        except ValueError:
            raise ValidationError("RUT inválido.")

        if not base.isdigit() or len(base) < 6:
            raise ValidationError("RUT inválido.")

        if _rut_calc_dv(base) != dv:
            raise ValidationError("Dígito verificador incorrecto.")

        # Unicidad ignorando formato
        qs = Estudiante.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for e in qs.only("rut"):
            if _rut_igual(e.rut, rut_norm):
                raise ValidationError("Ya existe un estudiante con ese RUT.")

        return rut_norm  # guardaremos normalizado

    def clean_apoderado_rut(self):
        rut = (self.cleaned_data.get("apoderado_rut") or "").strip()
        if not rut:
            return ""  # opcional para mayores
        rut_norm = _rut_normaliza(rut)
        try:
            base, dv = rut_norm.split("-")
        except ValueError:
            raise ValidationError("RUT de apoderado inválido.")
        if not base.isdigit() or _rut_calc_dv(base) != dv:
            raise ValidationError("RUT de apoderado inválido.")
        return rut_norm

    # ---------- Reglas de negocio ----------
    def clean(self):
        cleaned = super().clean()
        fnac = cleaned.get("fecha_nacimiento")
        if fnac:
            from datetime import date
            hoy = date.today()
            edad = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))
        else:
            edad = None

        if edad is not None and edad < 18:
            if not (cleaned.get("apoderado_nombre") or "").strip():
                self.add_error("apoderado_nombre", "Obligatorio para menores de edad.")
            if not (cleaned.get("apoderado_telefono") or "").strip():
                self.add_error("apoderado_telefono", "Obligatorio para menores de edad.")
            if not (cleaned.get("apoderado_rut") or "").strip():
                self.add_error("apoderado_rut", "Obligatorio para menores de edad.")

        # Punto 3: totalmente opcional. Si NO marcaron el check,
        # sólo validamos coherencia si escribieron algo.
        if not cleaned.get("sin_info_deportiva"):
            if cleaned.get("pertenece_organizacion") and not (
                cleaned.get("club_nombre") or ""
            ).strip():
                self.add_error("club_nombre", "Indica el nombre del club.")
            if cleaned.get("logro_nacional") or cleaned.get("logro_internacional"):
                if not (cleaned.get("categoria_competida") or "").strip():
                    self.add_error(
                        "categoria_competida", "Completa la categoría en la cual compitió."
                    )
                if not (cleaned.get("puntaje_o_logro") or "").strip():
                    self.add_error(
                        "puntaje_o_logro", "Indica el puntaje o logro obtenido."
                    )

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        # Normaliza RUT
        obj.rut = _rut_normaliza(self.cleaned_data["rut"])

        # Si marcaron "sin info deportiva", limpiamos campos deportivos
        if self.cleaned_data.get("sin_info_deportiva"):
            obj.pertenece_organizacion = False
            obj.club_nombre = ""
            obj.logro_nacional = False
            obj.logro_internacional = False
            obj.categoria_competida = ""
            obj.puntaje_o_logro = ""

        if commit:
            obj.save()
            self.save_m2m()
        return obj

# =========================================================
#                          DEPORTE
# =========================================================
class DeporteForm(forms.ModelForm):
    class Meta:
        model = Deporte
        fields = ["nombre", "categoria", "equipamiento"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "equipamiento": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ['titulo', 'cuerpo', 'dirigido_a', 'autor']
        widgets = {
            'dirigido_a': forms.Select(attrs={'class': 'form-control'}),
        }