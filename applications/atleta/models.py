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

    # Relación con el usuario (nombres, email, etc.)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={'tipo_usuario': 'ATLE'}
    )

    # Identificación del/la atleta
    rut = models.CharField(max_length=12, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=80, blank=True)
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)

    # Clasificación/estado
    tipo_atleta = models.CharField(max_length=3, choices=TipoAtleta.choices, default=TipoAtleta.BECADO)
    estado = models.CharField(max_length=50, blank=True)
    faltas_consecutivas = models.IntegerField(default=0)

    # Tutor / representante legal
    apoderado = models.ForeignKey('usuarios.Apoderado', on_delete=models.SET_NULL, null=True, blank=True)

    # Información deportiva (postulación/logros)
    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True)
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)
    categoria_competida = models.CharField(max_length=80, blank=True)
    puntaje_o_logro = models.CharField(max_length=120, blank=True)

    def __str__(self):
        try:
            nombre = self.usuario.get_full_name()
        except AttributeError:
            nombre = str(self.usuario)
        return f"{nombre} ({self.rut})"

    # --------- utilidades internas ----------
    def _calc_edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        e = hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
        return max(e, 0)

    # --------- validaciones de negocio ----------
    def clean(self):
        # Menores de edad: apoderado obligatorio
        edad_tmp = self._calc_edad()
        if edad_tmp is not None and edad_tmp < 18 and not self.apoderado:
            raise ValidationError("Para menores de edad, debe registrar un apoderado.")

        # Si pertenece a organización, el club es obligatorio
        if self.pertenece_organizacion and not self.club_nombre:
            raise ValidationError("Si pertenece a una organización deportiva, indique el nombre del club.")

        # Si marca logros, sugiero completar categoría/puntaje
        if (self.logro_nacional or self.logro_internacional) and (not self.categoria_competida or not self.puntaje_o_logro):
            raise ValidationError("Si declaró logros, complete la categoría y el puntaje o logro obtenido.")

    # --------- persistencia ----------
    def save(self, *args, **kwargs):
        self.edad = self._calc_edad()
        super().save(*args, **kwargs)


class Inscripcion(models.Model):
    atleta = models.ForeignKey("atleta.Atleta", on_delete=models.CASCADE, related_name="inscripciones")
    # Dejar null=True/blank=True si tienes datos previos sin curso; luego puedes hacerlo obligatorio
    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE, related_name="inscripciones", null=True,
                              blank=True)
    fecha  = models.DateField(default=timezone.now)
    estado = models.CharField(
        max_length=20,
        choices=[("ACTIVA", "Activa"), ("INACTIVA", "Inactiva")],
        default="ACTIVA",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["atleta", "curso"], name="uniq_inscripcion_atleta_curso")
        ]

    def __str__(self):
        return f"{self.atleta} → {self.curso}"


class Clase(models.Model):
    # Hacemos null=True/blank=True para migrar sin prompt; luego puedes quitarlo cuando completes datos
    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE, related_name="clases", null=True, blank=True)
    profesor = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tema = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        # Evita fallar si curso está NULL temporalmente
        curso_txt = str(self.curso) if self.curso else "—"
        return f"{curso_txt} - {self.tema} ({self.fecha})"

class AsistenciaAtleta(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name='asistencias')
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='asistencias', null=True, blank=True)
    presente = models.BooleanField(default=False)
    observaciones = models.CharField(max_length=200, blank=True)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asistencias_registradas'
    )
    registrada_en = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clase", "atleta"], name="uniq_asistencia_atleta_por_clase")
        ]

    def __str__(self):
        return f"{self.atleta} - {self.clase} : {'Presente' if self.presente else 'Ausente'}"


class AsistenciaProfesor(models.Model):
    profesor = models.ForeignKey('usuarios.Profesor', on_delete=models.CASCADE)
    # Default para no pedir valor en migración
    fecha = models.DateField(default=timezone.now)
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profesor", "fecha"], name="uniq_asistencia_profesor_fecha")
        ]

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
