# applications/pmul/models.py
from datetime import datetime, timedelta, time

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError

from applications.core.models import Estudiante

Usuario = settings.AUTH_USER_MODEL


ESPECIALIDADES = [
    ("NUT", "Nutricionista"),
    ("KIN", "Kinesiólogo/a"),
    ("TENS", "TENS"),
    ("COORD", "Coordinador/a"),
    ("APOYO", "Apoyo deportivo"),
    ("TSOC", "Trabajador/a social"),
    ("OTRA", "Otra"),
]

PISOS = [
    (1, "Primer piso"),
    (2, "Segundo piso"),
]


def piso_por_especialidad(code: str) -> int:
    """Determina automáticamente el piso según la especialidad."""
    if code in {"NUT", "KIN"}:
        return 1
    return 2


class ProfesionalPerfil(models.Model):

    user = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="perfil_pmul")
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA")

    def piso_predeterminado(self) -> int:
        return piso_por_especialidad(self.especialidad)

    def __str__(self):
        return f"{self.user} · {self.get_especialidad_display()}"



class Cita(models.Model):
    ESTADOS = [
        ("PEND", "Pendiente"),
        ("REAL", "Atendida"),
        ("REPROG", "Reprogramada"),
        ("CANC", "Cancelada"),
    ]

    paciente = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="citas")
    profesional = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="citas_pmul")
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA", editable=False)
    piso = models.PositiveSmallIntegerField(choices=PISOS, default=1, editable=False)
    estado = models.CharField(max_length=6, choices=ESTADOS, default="PEND")
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.paciente} · {self.inicio:%d/%m %H:%M}"


    def clean(self):
        super().clean()


        if self.fin and self.fin <= self.inicio:
            raise ValidationError({"fin": "La hora de término debe ser posterior al inicio."})


        if self.inicio and self.inicio < timezone.now():
            raise ValidationError({"inicio": "No puedes agendar en el pasado."})


        activos = ~Q(estado="CANC")


        if self.paciente_id and self.inicio:
            qs = Cita.objects.filter(
                paciente_id=self.paciente_id,
                inicio__date=self.inicio.date(),
            ).filter(activos)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"inicio": "El deportista ya tiene una cita ese día."})

        # 2) Evitar solapamiento para el MISMO profesional (citas activas)
        if self.profesional_id and self.inicio and self.fin:
            qs = Cita.objects.filter(
                profesional_id=self.profesional_id
            ).filter(activos).filter(
                inicio__lt=self.fin,
                fin__gt=self.inicio,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Se solapa con otra cita del profesional en ese horario.")


    def save(self, *args, **kwargs):
        # Autocompletar especialidad/piso según perfil del profesional
        try:
            esp = self.profesional.perfil_pmul.especialidad
        except Exception:
            esp = "OTRA"
        self.especialidad = esp
        self.piso = piso_por_especialidad(esp)
        super().save(*args, **kwargs)



class FichaClinica(models.Model):
    ESTADOS_FICHA = [
        ("FIN", "Finalizada"),
        ("SEG", "En seguimiento"),
    ]

    paciente = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="fichas")
    profesional = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="fichas_pmul")
    fecha = models.DateField(auto_now_add=True)
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA", editable=False)
    motivo = models.CharField(max_length=200, blank=True)
    observaciones = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    estado = models.CharField(max_length=3, choices=ESTADOS_FICHA, default="FIN")

    # publicación por rol (visibilidad)
    publicar_profesor = models.BooleanField(default=False)
    publicar_coordinador = models.BooleanField(default=True)
    publicar_admin = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        try:
            esp = self.profesional.perfil_pmul.especialidad
        except Exception:
            esp = "OTRA"
        self.especialidad = esp
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ficha {self.paciente} {self.fecha:%d/%m/%Y}"



class FichaAdjunto(models.Model):
    ficha = models.ForeignKey(FichaClinica, on_delete=models.CASCADE, related_name="adjuntos")
    archivo = models.FileField(upload_to="fichas_adjuntos/")
    nombre = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nombre or self.archivo.name



class Disponibilidad(models.Model):
    """
    Franja disponible publicada por el profesional PMUL.
    - Cuando alguien reserva, se crea una Cita y el slot pasa a 'RESERVADA'.
    - Se bloquean solapamientos entre disponibilidades del mismo profesional.
    """
    class Estado(models.TextChoices):
        LIBRE     = "LIBRE", "Libre para reservar"
        RESERVADA = "RESERV", "Reservada"
        CANCELADA = "CANC", "Cancelada"

    profesional = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="disponibilidades",
        limit_choices_to={"tipo_usuario": "PMUL"},
    )
    inicio = models.DateTimeField()
    fin    = models.DateTimeField()
    piso   = models.CharField(max_length=20, blank=True, default="")
    estado = models.CharField(max_length=6, choices=Estado.choices, default=Estado.LIBRE)
    notas  = models.CharField(max_length=200, blank=True, default="")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["inicio"]
        constraints = [
            models.UniqueConstraint(fields=["profesional", "inicio"], name="uniq_prof_slot_inicio"),
        ]
        indexes = [
            models.Index(fields=["profesional", "inicio"]),
        ]

    def __str__(self):
        return f"{self.profesional} · {self.inicio:%d/%m %H:%M}-{self.fin:%H:%M} ({self.get_estado_display()})"

    def clean(self):
        # Solo validar si ambos campos están definidos
        if self.inicio and self.fin:
            if self.fin <= self.inicio:
                raise ValidationError("La hora de fin debe ser posterior a la de inicio.")


        if self.profesional_id and self.inicio and self.fin:
            qs = Disponibilidad.objects.filter(
                profesional_id=self.profesional_id,
                estado__in=[self.Estado.LIBRE, self.Estado.RESERVADA],
                inicio__lt=self.fin,
                fin__gt=self.inicio,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Ya tienes otra franja publicada que se solapa con este horario.")

    @classmethod
    def generar_lote(
            cls,
            *,
            profesional,
            fecha_inicio,  # date
            fecha_fin,  # date (incluido)
            dias_semana,  # list[int] -> 0=lu ... 6=do
            hora_inicio_dia,  # time
            hora_fin_dia,  # time
            duracion_min: int,
            intervalo_min: int,
            pausas=None,  # list[tuple[time, time]] opcional
            piso="",
            notas="",
            estado=None,  # si None => LIBRE
    ):

        tz = timezone.get_current_timezone()

        def aware_dt(d: datetime.date, t: datetime.time) -> datetime:
            # Asegura que el time sea ingenuo y lo convierte a 'aware' con la zona del proyecto
            nt = t.replace(tzinfo=None)
            naive = datetime.combine(d, nt)
            return timezone.make_aware(naive, tz)

        if not estado:
            estado = cls.Estado.LIBRE

        creados, omitidos = 0, 0
        dia = fecha_inicio
        one_day = timedelta(days=1)

        while dia <= fecha_fin:
            if dia.weekday() in dias_semana:

                # generador de punteros de tiempo dentro del día
                puntero = datetime.combine(dia, hora_inicio_dia)
                fin_jornada = datetime.combine(dia, hora_fin_dia)

                while puntero < fin_jornada:
                    ini_dt = puntero
                    fin_dt = ini_dt + timedelta(minutes=duracion_min)

                    # si se pasa del fin de jornada, corta
                    if fin_dt > fin_jornada:
                        break

                    # respeta pausas (si hay)
                    en_pausa = False
                    if pausas:
                        for (p_ini, p_fin) in pausas:
                            p_i = datetime.combine(dia, p_ini)
                            p_f = datetime.combine(dia, p_fin)
                            # solape con la pausa:
                            if ini_dt < p_f and fin_dt > p_i:
                                en_pausa = True
                                # salta el puntero al final de la pausa
                                puntero = max(puntero, p_f)
                                break
                    if en_pausa:
                        continue

                    # convierte a aware con tz del proyecto
                    ini_aw = timezone.make_aware(ini_dt, tz)
                    fin_aw = timezone.make_aware(fin_dt, tz)

                    # evita solapes con otros slots LIBRE/RESERVADA del mismo profesional
                    choque = cls.objects.filter(
                        profesional=profesional,
                        estado__in=[cls.Estado.LIBRE, cls.Estado.RESERVADA],
                        inicio__lt=fin_aw, fin__gt=ini_aw,
                    ).exists()

                    if not choque:
                        cls.objects.create(
                            profesional=profesional,
                            inicio=ini_aw,
                            fin=fin_aw,
                            piso=str(piso or ""),
                            estado=estado,
                            notas=notas or "",
                        )
                        creados += 1
                    else:
                        omitidos += 1

                    # avanza por intervalo (duración + separación entre slots)
                    puntero = fin_dt + timedelta(minutes=intervalo_min)

            dia += one_day

        return creados, omitidos

    @property
    def duracion_min(self):
        return int((self.fin - self.inicio).total_seconds() // 60)
