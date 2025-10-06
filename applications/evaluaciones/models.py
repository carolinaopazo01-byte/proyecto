from django.db import models
from django.conf import settings
from applications.atleta.models import Atleta

Usuario = settings.AUTH_USER_MODEL

class Planificacion(models.Model):
    nombre = models.CharField(max_length=150)
    contenido = models.TextField(blank=True)
    metodologia = models.CharField(max_length=150, blank=True)
    duracion = models.DurationField(null=True, blank=True)
    nivel_dificultad = models.CharField(max_length=50, blank=True)
    profesor = models.ForeignKey('usuarios.Profesor', on_delete=models.SET_NULL, null=True, blank=True)
    mes = models.DateField(help_text="Usar el día 1 del mes planificado (ej. 2025-09-01)")

    def __str__(self):
        return f"{self.nombre} ({self.mes})"


class Objetivo(models.Model):
    planificacion = models.ForeignKey(Planificacion, on_delete=models.CASCADE, related_name='objetivos')
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=50, blank=True)
    logrado = models.BooleanField(default=False)

    def __str__(self):
        return f"Obj {self.planificacion}: {self.descripcion[:30]}"


class Material(models.Model):
    nombre = models.CharField(max_length=100)
    cantidad = models.IntegerField(default=0)
    estado = models.CharField(max_length=50, blank=True)
    ubicacion = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.nombre


class PlanificacionMaterial(models.Model):
    planificacion = models.ForeignKey(Planificacion, on_delete=models.CASCADE, related_name='materiales')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    cantidad_necesario = models.IntegerField(default=1)


class Evaluacion(models.Model):
    class Tipo(models.TextChoices):
        KINESIO = 'KIN', 'Kinesiología'
        PSICO = 'PSI', 'Psicología'
        NUTRI = 'NUT', 'Nutrición'
        TENS = 'TEN', 'TENS'
        OTRO = 'OTR', 'Otro'

    tipo_evaluacion = models.CharField(max_length=3, choices=Tipo.choices)
    fecha = models.DateField()
    resultados = models.CharField(max_length=200, blank=True)
    observaciones = models.TextField(blank=True)
    recomendaciones = models.TextField(blank=True)
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name='evaluaciones')
    profesional = models.ForeignKey('usuarios.ProfesionalMulti', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.get_tipo_evaluacion_display()} - {self.atleta} ({self.fecha})"


class Cita(models.Model):
    profesional = models.ForeignKey('usuarios.ProfesionalMulti', on_delete=models.CASCADE)
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    motivo = models.CharField(max_length=150, blank=True)
    notas = models.TextField(blank=True)
    confirmada = models.BooleanField(default=False)

    class Meta:
        unique_together = ('profesional', 'fecha')

    def __str__(self):
        return f"Cita {self.profesional} con {self.atleta} en {self.fecha}"
