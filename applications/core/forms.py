from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db import models
from django.apps import apps

# Importa sólo modelos que no generan ciclos directos
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
    # Coherente con modelo (capacidad puede ir vacía)
    capacidad = forms.IntegerField(required=False, min_value=0, label="Capacidad")

    # Campo oculto con default (si no viene en el POST, se pone 150)
    radio_metros = forms.IntegerField(
        required=False,
        min_value=1,
        initial=150,
        widget=forms.HiddenInput()  # <-- paréntesis corregidos
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
        labels = {
            "radio_metros": "Radio de validación (m)",
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

    def clean_comuna(self):
        return (self.cleaned_data.get("comuna") or "").strip()

    def clean_capacidad(self):
        v = self.cleaned_data.get("capacidad")
        if v in ("", None):
            return None
        if v < 0:
            raise ValidationError("La capacidad no puede ser negativa.")
        return v

    def clean_radio_metros(self):
        v = self.cleaned_data.get("radio_metros")
        return 150 if v in (None, "") else v

# ========================= Curso y horarios =========================
class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nombre",
            "programa",
            "disciplina",
            "categoria",
            "sede",
            "fecha_inicio",
            "fecha_termino",
            "profesor",
            "profesores_apoyo",
            "cupos",
            "cupos_espera",
            "permitir_inscripcion_rapida",
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

# ========================= Inscripción a curso =========================
if InscripcionCursoModel is not None:
    class InscripcionCursoForm(forms.ModelForm):
        class Meta:
            model = InscripcionCursoModel
            fields = ["estudiante", "curso"]
            labels = {"estudiante": "Estudiante", "curso": "Curso"}

        def clean(self):
            cleaned = super().clean()
            # Forzar validaciones del modelo (UniqueConstraint, etc.)
            inst = self.instance if getattr(self, "instance", None) else InscripcionCursoModel()
            for k, v in cleaned.items():
                setattr(inst, k, v)
            inst.full_clean(exclude=None)
            return cleaned
else:
    class InscripcionCursoForm(forms.Form):
        estudiante = forms.ModelChoiceField(queryset=Estudiante.objects.all(), label="Estudiante")
        curso = forms.ModelChoiceField(queryset=Curso.objects.all(), label="Curso")

        def clean(self):
            cleaned = super().clean()
            estudiante = cleaned.get("estudiante")
            curso = cleaned.get("curso")
            if not estudiante or not curso:
                return cleaned
            model = _get_model('core', 'InscripcionCurso')
            if model:
                exists = model.objects.filter(estudiante=estudiante, curso=curso).exists()
                if exists:
                    raise ValidationError("El/la estudiante ya está inscrito/a en ese curso.")
            return cleaned

        def save(self, commit=True):
            model = _get_model('core', 'InscripcionCurso')
            if not model:
                raise ValidationError("No se pudo crear la inscripción (modelo no disponible).")
            obj = model(estudiante=self.cleaned_data["estudiante"], curso=self.cleaned_data["curso"])
            if commit:
                obj.full_clean()
                obj.save()
            return obj

# ========================= Estudiante =========================
class EstudianteForm(forms.ModelForm):
    """
    Se piden datos de tutor/a SOLO si el/la estudiante es menor de 18 años.
    Además, el modelo incluye apoderado_email y apoderado_fecha_nacimiento.
    """
    class Meta:
        model = Estudiante
        fields = [
            "rut", "nombres", "apellidos", "fecha_nacimiento",
            "direccion", "comuna", "telefono", "email",
            "n_emergencia", "prevision",
            "apoderado_nombre", "apoderado_telefono", "apoderado_rut",
            "apoderado_email", "apoderado_fecha_nacimiento",   # <-- añadidos
            "pertenece_organizacion", "club_nombre",
            "logro_nacional", "logro_internacional",
            "categoria_competida", "puntaje_o_logro",
            "curso", "activo",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "apoderado_fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "rut": "RUT",
            "direccion": "Dirección",
            "comuna": "Comuna",
            "telefono": "Teléfono",
            "email": "Email",
            "n_emergencia": "Número de emergencia",
            "prevision": "Previsión de salud",
            "apoderado_nombre": "Nombre del/la tutor(a)",
            "apoderado_telefono": "Teléfono del/la tutor(a)",
            "apoderado_rut": "RUT del/la tutor(a)",
            "apoderado_email": "Correo electrónico del/la tutor(a)",
            "apoderado_fecha_nacimiento": "Fecha de nacimiento del/la tutor(a)",
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
        rut_norm = _rut_normaliza(rut)
        try:
            base, dv = rut_norm.split("-")
        except ValueError:
            raise ValidationError("RUT inválido.")
        if not base.isdigit() or len(base) < 6:
            raise ValidationError("RUT inválido.")
        if _rut_calc_dv(base) != dv:
            raise ValidationError("Dígito verificador incorrecto.")

        qs = Estudiante.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for e in qs.only("rut"):
            if _rut_igual(e.rut, rut_norm):
                raise ValidationError("Ya existe un estudiante con ese RUT.")
        return rut_norm

    def clean_apoderado_rut(self):
        rut = (self.cleaned_data.get("apoderado_rut") or "").strip()
        if not rut:
            return ""
        rut_norm = _rut_normaliza(rut)
        try:
            base, dv = rut_norm.split("-")
        except ValueError:
            raise ValidationError("RUT de apoderado inválido.")
        if not base.isdigit() or _rut_calc_dv(base) != dv:
            raise ValidationError("RUT de apoderado inválido.")
        return rut_norm

    def clean(self):
        cleaned = super().clean()

        # Edad para reglas de apoderado por minoría de edad (solo si < 18)
        fnac = cleaned.get("fecha_nacimiento")
        if fnac:
            hoy = timezone.localdate()
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
            if not (cleaned.get("apoderado_email") or "").strip():
                self.add_error("apoderado_email", "Obligatorio para menores de edad.")
            if not cleaned.get("apoderado_fecha_nacimiento"):
                self.add_error("apoderado_fecha_nacimiento", "Obligatorio para menores de edad.")

        # Reglas deportivas condicionales
        if cleaned.get("pertenece_organizacion") and not (cleaned.get("club_nombre") or "").strip():
            self.add_error("club_nombre", "Indica el nombre del club.")
        if cleaned.get("logro_nacional") or cleaned.get("logro_internacional"):
            if not (cleaned.get("categoria_competida") or "").strip():
                self.add_error("categoria_competida", "Completa la categoría en la cual compitió.")
            if not (cleaned.get("puntaje_o_logro") or "").strip():
                self.add_error("puntaje_o_logro", "Indica el puntaje o logro obtenido.")

        return cleaned

# ========================= Deporte =========================
class DeporteForm(forms.ModelForm):
    class Meta:
        model = Deporte
        fields = ["nombre", "categoria", "equipamiento"]

# ========================= Comunicado =========================
class ComunicadoForm(forms.ModelForm):
    audiencia_codigos = forms.MultipleChoiceField(
        choices=[(c, c) for c in AUDIENCIA_CODIGOS],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Dirigido a (códigos)"
    )

    class Meta:
        model = Comunicado
        fields = ['titulo', 'cuerpo', 'autor', 'audiencia_codigos', 'audiencia_roles']
        widgets = {
            'audiencia_roles': forms.SelectMultiple(attrs={'size': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and (self.instance.audiencia_codigos or "").strip():
            self.initial['audiencia_codigos'] = [
                c for c in (self.instance.audiencia_codigos or "").split(",") if c
            ]

    def clean_audiencia_codigos(self):
        cods = self.cleaned_data.get("audiencia_codigos") or []
        cods = [c for c in cods if c in AUDIENCIA_CODIGOS]
        return ",".join(sorted(set(cods)))

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
            widgets = {
                "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
                "comentarios": forms.Textarea(attrs={"rows": 4}),
            }
            labels = {
                "deporte_interes": "Deporte de interés",
                "sede_interes": "Sede de interés",
                "comentarios": "Comentarios / Observaciones",
            }
else:
    class RegistroPublicoForm(forms.Form):
        rut = forms.CharField()
        nombres = forms.CharField()
        apellidos = forms.CharField()
        fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)
        email = forms.EmailField(required=False)
        telefono = forms.CharField(required=False)
        comuna = forms.CharField(required=False)
        deporte_interes = forms.ModelChoiceField(queryset=Deporte.objects.all(), required=False)
        sede_interes = forms.ModelChoiceField(queryset=Sede.objects.all(), required=False)
        comentarios = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=False)

        def save(self, commit=True):
            model = _get_model('core', 'PostulacionEstudiante')
            if not model:
                raise ValidationError("No se pudo crear la postulación (modelo no disponible).")
            obj = model(**self.cleaned_data)
            if commit:
                obj.full_clean()
                obj.save()
            return obj

# ========================= Noticia (por si tu vista lo usa) =========================
if NoticiaModel is not None:
    class NoticiaForm(forms.ModelForm):
        class Meta:
            model = NoticiaModel
            fields = ["titulo", "bajada", "cuerpo", "imagen", "publicada"]

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
