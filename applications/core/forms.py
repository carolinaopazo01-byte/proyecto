from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db import models
from django.apps import apps

# Importa solo modelos que no generan ciclos directos
from .models import (
    Sede,
    Comunicado,
    Estudiante,
    Curso,
    Planificacion,
    Deporte,
    CursoHorario,
    AUDIENCIA_CODIGOS,
    RegistroPeriodo,
)

# ======= helpers seguros para get_model (evita caídas en import) =======
def _get_model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

InscripcionCursoModel = _get_model('core', 'InscripcionCurso')
PostulacionEstudianteModel = _get_model('core', 'PostulacionEstudiante')
NoticiaModel = _get_model('core', 'Noticia')  # por si usas NoticiaForm en views

# ========================= utilidades =========================
MAX_MB = 10
ALLOWED_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}

def _monday(d):
    return d - timedelta(days=d.weekday())

# ========================= Planificación =========================
class PlanificacionUploadForm(forms.ModelForm):
    semana = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Semana (elige cualquier día de la semana; se ajustará al lunes)"
    )
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

        qs = (Curso.objects
                    .select_related("sede", "disciplina", "profesor")
                    .order_by("sede__nombre", "disciplina__nombre", "nombre"))
        if user and getattr(user, "tipo_usuario", "") == "PROF":
            qs = qs.filter(models.Q(profesor=user) | models.Q(profesores_apoyo=user)).distinct()
        self.fields["curso"].queryset = qs

        if not self.initial.get("semana"):
            self.initial["semana"] = timezone.localdate()

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

# ========================= RUT helpers =========================
def _rut_normaliza(rut: str) -> str:
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

# ========================= Sede =========================
class SedeForm(forms.ModelForm):
    capacidad = forms.IntegerField(required=False, min_value=0, label="Capacidad")
    radio_metros = forms.IntegerField(
        required=False,
        min_value=1,
        initial=150,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Sede
        fields = ["nombre", "comuna", "direccion",
                  "latitud", "longitud", "radio_metros",
                  "capacidad", "activa", "descripcion"]
        widgets = {
            "latitud": forms.HiddenInput(),
            "longitud": forms.HiddenInput(),
        }

    def clean_nombre(self):
        v = (self.cleaned_data.get("nombre") or "").strip()
        if not v:
            raise ValidationError("El nombre es obligatorio.")
        return v

    def clean_direccion(self):
        v = (self.cleaned_data.get("direccion") or "").strip()
        if not v:
            raise ValidationError("La dirección es obligatoria.")
        return v

# ========================= Curso y horarios =========================
class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nombre", "programa", "disciplina", "categoria", "sede",
            "fecha_inicio", "fecha_termino",
            "profesor", "profesores_apoyo",
            "cupos", "cupos_espera", "permitir_inscripcion_rapida",
            "publicado", "estado",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_termino": forms.DateInput(attrs={"type": "date"}),
            "profesores_apoyo": forms.SelectMultiple(attrs={"size": 6}),
        }

    def clean(self):
        data = super().clean()
        ini, fin = data.get("fecha_inicio"), data.get("fecha_termino")
        if ini and fin and fin < ini:
            self.add_error("fecha_termino", "La fecha de término debe ser ≥ a la fecha de inicio.")
        return data

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

# ========================= Estudiante =========================
class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "rut", "nombres", "apellidos", "fecha_nacimiento",
            "direccion", "comuna", "telefono", "email",
            "n_emergencia", "prevision",
            "apoderado_nombre", "apoderado_telefono", "apoderado_rut",
            "apoderado_email", "apoderado_fecha_nacimiento",
            "pertenece_organizacion", "club_nombre",
            "logro_nacional", "logro_internacional",
            "categoria_competida", "puntaje_o_logro",
            "curso", "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "apoderado_fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }

# ========================= Deporte =========================
class DeporteForm(forms.ModelForm):
    class Meta:
        model = Deporte
        fields = ["nombre", "categoria", "equipamiento"]

# ========================= Comunicado =========================

class ComunicadoForm(forms.ModelForm):
    audiencia_codigos = forms.MultipleChoiceField(
        label="Audiencia",
        choices=[
            ("ATLE", "Deportistas Alto Rendimiento"),
            ("PMUL", "Profesionales multidisciplinarios"),
            ("APOD", "Apoderados"),
            ("PUBL", "Público general"),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Comunicado
        fields = ["titulo", "cuerpo", "audiencia_codigos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["audiencia_codigos"] = self.instance.get_audiencia_codigos()

    def save(self, commit=True):
        instance = super().save(commit=False)
        codigos = self.cleaned_data.get("audiencia_codigos", [])
        instance.set_audiencia_codigos(codigos)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

# ========================= Registro público (Postulación) =========================
if PostulacionEstudianteModel is not None:
    class RegistroPublicoForm(forms.ModelForm):
        class Meta:
            model = PostulacionEstudianteModel
            fields = [
                "rut", "nombres", "apellidos", "fecha_nacimiento",
                "email", "telefono", "comuna",
                "deporte_interes", "sede_interes",
                "comentarios",
            ]
else:
    class RegistroPublicoForm(forms.Form):
        pass

# ========================= Noticia =========================
if NoticiaModel is not None:
    class NoticiaForm(forms.ModelForm):
        class Meta:
            model = NoticiaModel
            fields = ["titulo", "bajada", "cuerpo", "imagen", "publicada"]
            labels = {
                "titulo": "Título",
                "bajada": "Bajada / subtítulo",
                "cuerpo": "Cuerpo del texto",
                "imagen": "Imagen destacada",
                "publicada": "¿Publicada?",
            }
            widgets = {
                "bajada": forms.Textarea(attrs={"rows": 3}),
                "cuerpo": forms.Textarea(attrs={"rows": 8}),
            }

# ========================= RegistroPeriodo =========================
class RegistroPeriodoForm(forms.ModelForm):
    class Meta:
        model = RegistroPeriodo
        fields = ["nombre", "inicio", "fin", "estado", "activo"]

    def clean(self):
        data = super().clean()
        ini, fin = data.get("inicio"), data.get("fin")
        if ini and fin and fin < ini:
            self.add_error("fin", "La fecha de término debe ser ≥ a la fecha de inicio.")
        return data
