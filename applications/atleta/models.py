from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from applications.core.models import SedeDeporte
from datetime import date

Usuario = settings.AUTH_USER_MODEL


class Atleta(models.Model):
    class TipoAtleta(models.TextChoices):
        BECADO = 'BEC', 'Becado'
        ALTO_REND = 'AR', 'Alto rendimiento'

    # Relación con el usuario (nombres, email, etc. suelen vivir ahí)
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={'tipo_usuario': 'ATLE'}
    )

    # Identificación del/la atleta
    rut = models.CharField(max_length=12, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=80, blank=True)  # NUEVO
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)  # NUEVO (autocalculada)

    # Clasificación/estado
    tipo_atleta = models.CharField(max_length=3, choices=TipoAtleta.choices, default=TipoAtleta.BECADO)
    estado = models.CharField(max_length=50, blank=True)
    faltas_consecutivas = models.IntegerField(default=0)

    # Tutor / representante legal (ya existente)
    apoderado = models.ForeignKey('usuarios.Apoderado', on_delete=models.SET_NULL, null=True, blank=True)

    # 3) Información deportiva del atleta (NUEVO)
    # Ojo: Inscripción ya amarra a SedeDeporte/Deporte; estos campos son de "postulación/logros"
    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True)
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)
    categoria_competida = models.CharField(max_length=80, blank=True)
    puntaje_o_logro = models.CharField(max_length=120, blank=True)

    def __str__(self):
        # get_full_name puede no existir si el user model es custom; si no, usa str(self.usuario)
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
        # calcula y persiste la edad siempre que haya fecha_nacimiento
        self.edad = self._calc_edad()
        super().save(*args, **kwargs)


class Inscripcion(models.Model):
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='inscripciones')
    sede_deporte = models.ForeignKey(SedeDeporte, on_delete=models.CASCADE, related_name='inscripciones')
    fecha = models.DateField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ('atleta', 'sede_deporte')

    def clean(self):
        if self.activa:
            ocupados = Inscripcion.objects.filter(
                sede_deporte=self.sede_deporte, activa=True
            ).exclude(pk=self.pk).count()
            if ocupados >= self.sede_deporte.cupos_max:
                raise ValidationError("No quedan cupos disponibles para esta disciplina en la sede.")

    def __str__(self):
        return f"{self.atleta} -> {self.sede_deporte}"


class Clase(models.Model):
    sede_deporte = models.ForeignKey(SedeDeporte, on_delete=models.CASCADE, related_name='clases')
    profesor = models.ForeignKey('usuarios.Profesor', on_delete=models.SET_NULL, null=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tema = models.CharField(max_length=150, blank=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.sede_deporte} / {self.fecha}"


class AsistenciaAtleta(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name='asistencias')
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='asistencias')
    presente = models.BooleanField(default=False)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('clase', 'atleta')

    def __str__(self):
        return f"{self.atleta} - {self.clase} : {'Presente' if self.presente else 'Ausente'}"


class AsistenciaProfesor(models.Model):
    profesor = models.ForeignKey('usuarios.Profesor', on_delete=models.CASCADE)
    fecha = models.DateField()
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('profesor', 'fecha')

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
