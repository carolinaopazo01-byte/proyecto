from django import forms
from django.utils import timezone

from applications.core.models import Estudiante  # ajusta si tu "paciente" tiene otro nombre
from .models import Cita, FichaClinica, FichaAdjunto, Disponibilidad
from datetime import datetime, timedelta   # 👈 AGREGA ESTO

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

class SlotForm(forms.ModelForm):
    class Meta:
        model = Disponibilidad
        fields = ["inicio", "fin", "piso", "notas"]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fin": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("inicio")
        fin = cleaned.get("fin")
        if ini and fin:
            if fin <= ini:
                self.add_error("fin", "Debe ser posterior al inicio.")
            if ini < timezone.now():
                self.add_error("inicio", "No puedes publicar en el pasado.")

            # Evitar solapes con OTRAS franjas del mismo profesional
            if self.instance.pk:
                qs_slots = Disponibilidad.objects.exclude(pk=self.instance.pk)
            else:
                qs_slots = Disponibilidad.objects.all()
            if ini and fin and self.initial.get("profesional"):
                prof = self.initial["profesional"]
            else:
                prof = getattr(self.instance, "profesional", None) or getattr(self, "user", None) or None
            if prof:
                choque = qs_slots.filter(
                    profesional=prof,
                    inicio__lt=fin, fin__gt=ini,
                ).exists()
                if choque:
                    self.add_error(None, "Se solapa con otra franja publicada.")

                # (opcional) Evitar solapes con citas existentes del profesional
                if Cita.objects.filter(
                        profesional=prof,
                        inicio__lt=fin, fin__gt=ini,
                ).exclude(estado="CANC").exists():
                    self.add_error(None, "Se solapa con una cita ya agendada.")

        return cleaned


class SlotRecurrenteForm(forms.Form):
    DIA_CHOICES = [
        (0, "Lunes"), (1, "Martes"), (2, "Miércoles"),
        (3, "Jueves"), (4, "Viernes"), (5, "Sábado"), (6, "Domingo"),
    ]
    # ✅ varios días
    dias_semana   = forms.MultipleChoiceField(
        choices=DIA_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Días"
    )
    # ✅ rango diario + frecuencia
    hora_inicio_dia = forms.TimeField(label="Hora inicio (día)", widget=forms.TimeInput(attrs={"type": "time"}))
    hora_fin_dia    = forms.TimeField(label="Hora término (día)", widget=forms.TimeInput(attrs={"type": "time"}))
    duracion_min    = forms.IntegerField(min_value=10, max_value=240, initial=30, label="Duración (min)")
    cada_min        = forms.IntegerField(min_value=5, max_value=240, initial=30, label="Cada (min)")
    semanas         = forms.IntegerField(min_value=1, max_value=12, initial=4)
    piso            = forms.CharField(max_length=20, required=False)
    notas           = forms.CharField(max_length=200, required=False, widget=forms.TextInput())

    def clean(self):
        cleaned = super().clean()
        hi = cleaned.get("hora_inicio_dia")
        hf = cleaned.get("hora_fin_dia")
        dur = cleaned.get("duracion_min")
        cad = cleaned.get("cada_min")

        if hi and hf and hf <= hi:
            self.add_error("hora_fin_dia", "Debe ser posterior a la hora de inicio.")
        if dur and cad and cad <= 0:
            self.add_error("cada_min", "Debe ser mayor a 0.")
        # evita bucles infinitos: frecuencia razonable vs duración
        if dur and cad and cad < 5:
            self.add_error("cada_min", "Frecuencia demasiado corta.")
        return cleaned

    def generar_slots(self, profesional):
        if not self.is_valid():
            return []

        dias       = [int(x) for x in self.cleaned_data["dias_semana"]]
        hi_dia     = self.cleaned_data["hora_inicio_dia"]
        hf_dia     = self.cleaned_data["hora_fin_dia"]
        dur_min    = int(self.cleaned_data["duracion_min"])
        cada_min   = int(self.cleaned_data["cada_min"])
        semanas    = int(self.cleaned_data["semanas"])
        piso       = self.cleaned_data.get("piso") or ""
        notas      = self.cleaned_data.get("notas") or ""

        hoy = timezone.localdate()
        dow_hoy = hoy.weekday()

        items = []
        for dow in dias:
            delta_dias = (dow - dow_hoy) % 7
            primera_fecha = hoy + timedelta(days=delta_dias)

            for w in range(semanas):
                d = primera_fecha + timedelta(weeks=w)

                # punteros dentro del día
                dt_inicio = timezone.make_aware(datetime.combine(d, hi_dia))
                dt_limite = timezone.make_aware(datetime.combine(d, hf_dia))

                while True:
                    dt_fin = dt_inicio + timedelta(minutes=dur_min)
                    if dt_fin > dt_limite:
                        break
                    items.append(Disponibilidad(
                        profesional=profesional,
                        inicio=dt_inicio,
                        fin=dt_fin,
                        piso=piso,
                        notas=notas,
                    ))
                    dt_inicio = dt_inicio + timedelta(minutes=cada_min)

        return items

    class DisponibilidadForm(forms.ModelForm):
        class Meta:
            model = Disponibilidad
            fields = ["inicio", "fin", "piso", "notas"]
            widgets = {
                "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                "fin": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            }
