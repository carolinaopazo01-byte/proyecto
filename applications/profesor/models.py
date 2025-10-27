# applications/profesor/models.py
from django.db import models
from django.conf import settings
from applications.core.models import Sede


class AsistenciaProfesor(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENT", "Entrada"
        SALIDA = "SAL", "Salida"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asistencias_profesor"
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name="asistencias_profesor"
    )
    fecha = models.DateField()
    hora = models.TimeField()
    tipo = models.CharField(max_length=3, choices=Tipo.choices)

    class Meta:
        verbose_name = "Asistencia del Profesor"
        verbose_name_plural = "Asistencias de Profesores"
        ordering = ["-fecha", "-hora"]

    def __str__(self):
        return f"{self.usuario} - {self.get_tipo_display()} ({self.fecha} {self.hora})"
