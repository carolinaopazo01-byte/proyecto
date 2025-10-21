# applications/core/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from datetime import date

from .models import Sede, Estudiante, Curso, Planificacion, Deporte, CursoHorario

from applications.usuarios.utils import normalizar_rut


class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ["nombre", "direccion", "comuna", "descripcion", "capacidad", "activa"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "capacidad": forms.NumberInput(attrs={"min": 0}),
        }
        labels = {
            "nombre": "Nombre",
            "direccion": "Dirección",
            "comuna": "Comuna",
            "descripcion": "Descripción (opcional)",
            "capacidad": "Capacidad (opcional)",
            "activa": "Activo",
        }


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            # 1) Identificación
            "nombre", "programa", "disciplina", "categoria", "sede",
            # 2) Calendario
            "fecha_inicio", "fecha_termino",
            # 3) Profesorado
            "profesor", "profesores_apoyo",
            # 4) Cupos e inscripciones
            "cupos", "cupos_espera", "permitir_inscripcion_rapida",
            # 5) Visibilidad/Estado
            "publicado", "estado",
            # Compatibilidad (antiguos) – se mantienen pero no se muestran en el template
            # "horario", "lista_espera",
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

# ====== utilidades RUT (validación y formato) ======
def _rut_calc_dv(numero: str) -> str:
    factores = [2, 3, 4, 5, 6, 7]
    s, i = 0, 0
    for d in reversed(numero):
        s += int(d) * factores[i]
        i = (i + 1) % len(factores)
    r = 11 - (s % 11)
    if r == 11:
        return "0"
    if r == 10:
        return "K"
    return str(r)


def _rut_formatea(ch: str) -> str:
    base = "".join([c for c in ch if c.isdigit()])
    dv = ch[-1].upper()
    partes = []
    while len(base) > 3:
        partes.insert(0, base[-3:])
        base = base[:-3]
    if base:
        partes.insert(0, base)
    return ".".join(partes) + "-" + dv


# --- Estudiante ---
class EstudianteForm(forms.ModelForm):
    """Formulario principal del Estudiante con secciones:
       1) Identificación del/la atleta
       2) Tutor (sólo si es menor de edad)
       3) Información deportiva
    """
    class Meta:
        model = Estudiante
        fields = [
            # 1) Identificación del/la atleta
            "rut",
            "nombres",
            "apellidos",
            "fecha_nacimiento",
            "direccion",          # NUEVO
            "comuna",             # NUEVO
            "telefono",
            "email",

            # 2) Tutor (si es menor de edad)
            "apoderado_nombre",
            "apoderado_telefono",

            # 3) Información deportiva
            "pertenece_organizacion",  # NUEVO (bool)
            "club_nombre",             # NUEVO
            "logro_nacional",          # NUEVO (bool)
            "logro_internacional",     # NUEVO (bool)
            "categoria_competida",     # NUEVO
            "puntaje_o_logro",         # NUEVO

            # Otros existentes
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

    # -------- RUT --------
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
        # Guardamos el rut exactamente como lo retornamos en clean_rut()
        obj.rut = self.cleaned_data["rut"]
        if commit:
            obj.save()
            self.save_m2m()
        return obj

    # -------- Reglas de negocio por secciones --------
    def clean(self):
        cleaned = super().clean()

        # 1) Edad (se calcula también en el modelo; aquí sólo para validar tutor)
        fnac = cleaned.get("fecha_nacimiento")
        edad = None
        if fnac:
            hoy = date.today()
            edad = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))

        # 2) Si es menor de edad -> apoderado obligatorio (al menos nombre y teléfono)
        if edad is not None and edad < 18:
            if not cleaned.get("apoderado_nombre"):
                self.add_error("apoderado_nombre", "Obligatorio para menores de edad.")
            if not cleaned.get("apoderado_telefono"):
                self.add_error("apoderado_telefono", "Obligatorio para menores de edad.")

        # 3) Información deportiva:
        pertenece = cleaned.get("pertenece_organizacion")
        club = cleaned.get("club_nombre")
        if pertenece and not club:
            self.add_error("club_nombre", "Si pertenece a una organización, indique el nombre del club.")

        if (cleaned.get("logro_nacional") or cleaned.get("logro_internacional")) and (
            not cleaned.get("categoria_competida") or not cleaned.get("puntaje_o_logro")
        ):
            self.add_error("categoria_competida", "Complete la categoría en la cual compitió.")
            self.add_error("puntaje_o_logro", "Indique el puntaje o logro obtenido.")

        return cleaned


# --- Planificación ---
class PlanificacionForm(forms.ModelForm):
    class Meta:
        model = Planificacion
        fields = ["nombre", "contenido", "metodologia", "duracion", "nivel_dificultad"]
        widgets = {
            "contenido": forms.Textarea(attrs={"rows": 4}),
            "metodologia": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "nombre": "Nombre",
            "contenido": "Contenido",
            "metodologia": "Metodología",
            "duracion": "Duración (HH:MM:SS)",
            "nivel_dificultad": "Nivel de dificultad",
        }


# --- Deporte ---
class DeporteForm(forms.ModelForm):
    class Meta:
        model = Deporte
        fields = ["nombre", "categoria", "equipamiento"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "equipamiento": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }