from django.db import models
from django.conf import settings
from applications.core.models import SedeDeporte

Usuario = settings.AUTH_USER_MODEL

class Atleta(models.Model):
    class TipoAtleta(models.TextChoices):
        BECADO = 'BEC', 'Becado'
        ALTO_REND = 'AR', 'Alto rendimiento'

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'tipo_usuario': 'ATLE'})
    rut = models.CharField(max_length=12, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    tipo_atleta = models.CharField(max_length=3, choices=TipoAtleta.choices, default=TipoAtleta.BECADO)
    estado = models.CharField(max_length=50, blank=True)
    faltas_consecutivas = models.IntegerField(default=0)
    apoderado = models.ForeignKey('usuarios.Apoderado', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.rut})"


class Inscripcion(models.Model):
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='inscripciones')
    sede_deporte = models.ForeignKey(SedeDeporte, on_delete=models.CASCADE, related_name='inscripciones')
    fecha = models.DateField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ('atleta', 'sede_deporte')

    def clean(self):
        if self.activa:
            ocupados = Inscripcion.objects.filter(sede_deporte=self.sede_deporte, activa=True).exclude(pk=self.pk).count()
            if ocupados >= self.sede_deporte.cupos_max:
                from django.core.exceptions import ValidationError
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
