from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import date
from django.utils import timezone

Usuario = settings.AUTH_USER_MODEL


class Atleta(models.Model):
    class TipoAtleta(models.TextChoices):
        BECADO = 'BEC', 'Becado'
        ALTO_REND = 'AR', 'Alto rendimiento'


    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={'tipo_usuario': 'ATLE'},
        null=True, blank=True
    )


    rut = models.CharField(max_length=12, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=80, blank=True)
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)


    tipo_atleta = models.CharField(max_length=3, choices=TipoAtleta.choices, default=TipoAtleta.BECADO)
    estado = models.CharField(max_length=50, blank=True)
    faltas_consecutivas = models.IntegerField(default=0)


    apoderado = models.ForeignKey('usuarios.Apoderado', on_delete=models.SET_NULL, null=True, blank=True)


    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True)
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)
    categoria_competida = models.CharField(max_length=80, blank=True)
    puntaje_o_logro = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["rut"]

    def __str__(self):
        try:
            nombre = self.usuario.get_full_name()
        except AttributeError:
            nombre = str(self.usuario) if self.usuario else "—"
        return f"{nombre} ({self.rut})"


    def _calc_edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        e = hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
        return max(e, 0)


    def clean(self):

        edad_tmp = self._calc_edad()
        if edad_tmp is not None and edad_tmp < 18 and not self.apoderado:
            raise ValidationError("Para menores de edad, debe registrar un apoderado.")

        # Si pertenece a organización, el club es obligatorio
        if self.pertenece_organizacion and not self.club_nombre:
            raise ValidationError("Si pertenece a una organización deportiva, indique el nombre del club.")

        # Si marca logros, sugerir completar categoría/puntaje
        if (self.logro_nacional or self.logro_internacional) and (
            not self.categoria_competida or not self.puntaje_o_logro
        ):
            raise ValidationError("Si declaró logros, complete la categoría y el puntaje o logro obtenido.")


    def save(self, *args, **kwargs):
        self.edad = self._calc_edad()
        super().save(*args, **kwargs)


class Inscripcion(models.Model):
    atleta = models.ForeignKey("atleta.Atleta", on_delete=models.CASCADE, related_name="inscripciones")
    # Dejar null=True/blank=True si tienes datos previos sin curso; luego puedes hacerlo obligatorio
    curso = models.ForeignKey(
        "core.Curso",
        on_delete=models.CASCADE,
        related_name="inscripciones",
        null=True, blank=True
    )
    fecha = models.DateField(default=timezone.now)
    estado = models.CharField(
        max_length=20,
        choices=[("ACTIVA", "Activa"), ("INACTIVA", "Inactiva")],
        default="ACTIVA",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["atleta", "curso"], name="uniq_inscripcion_atleta_curso")
        ]
        ordering = ["-fecha", "atleta_id"]

    def __str__(self):
        return f"{self.atleta} → {self.curso or '—'}"


class Clase(models.Model):

    sede_deporte = models.ForeignKey(
        "core.SedeDeporte",
        on_delete=models.PROTECT,            # protege historial de clases
        related_name="clases",
        null=True, blank=True               #
    )


    curso = models.ForeignKey(
        "core.Curso",
        on_delete=models.SET_NULL,          # no romper clase si borras un curso antiguo
        related_name="clases",
        null=True, blank=True
    )

    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tema = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    # Control de sesión de clase
    ESTADO = (
        ("PEND", "Pendiente"),
        ("ENCU", "En curso"),
        ("CERR", "Cerrada"),
    )
    estado = models.CharField(max_length=4, choices=ESTADO, default="PEND")
    inicio_real = models.DateTimeField(null=True, blank=True)
    fin_real = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "hora_inicio"]

    def __str__(self):
        etiqueta = self.tema or "Clase"
        if self.sede_deporte_id:
            return f"{etiqueta} · {self.sede_deporte.deporte} @ {self.sede_deporte.sede} ({self.fecha})"
        if self.curso_id:
            return f"{etiqueta} · {self.curso.disciplina} @ {self.curso.sede} ({self.fecha})"
        return f"{etiqueta} ({self.fecha})"


class AsistenciaAtleta(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name='asistencias')
    atleta = models.ForeignKey(
        "atleta.Atleta",
        on_delete=models.CASCADE,
        related_name='asistencias',
        null=True, blank=True  # TEMPORAL si aún hay datos sin referencia
    )
    presente = models.BooleanField(default=False)
    justificado = models.BooleanField(default=False)
    observaciones = models.CharField(max_length=200, blank=True)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asistencias_registradas'
    )
    registrada_en = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clase", "atleta"], name="uniq_asistencia_atleta_por_clase")
        ]
        ordering = ["-clase__fecha", "clase_id", "atleta_id"]

    def __str__(self):
        estado = "Presente" if self.presente else ("Justificado" if self.justificado else "Ausente")
        return f"{self.atleta} - {self.clase} : {estado}"


class AsistenciaProfesor(models.Model):
    profesor = models.ForeignKey('usuarios.Profesor', on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profesor", "fecha"], name="uniq_asistencia_profesor_fecha")
        ]
        ordering = ["-fecha", "profesor_id"]

    def __str__(self):
        return f"{self.profesor} {self.fecha}"


class Cita(models.Model):
    profesional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="citas_recibe")
    paciente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="citas_paciente")
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(max_length=20, default="agendada")  # agendada, realizada, cancelada
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-hora"]

    def __str__(self):
        return f"{self.fecha} {self.hora} · {self.profesional} con {self.paciente} ({self.estado})"
