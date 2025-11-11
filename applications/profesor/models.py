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

        related_name = "asistencias_prof",
        null = True, blank = True,
    )

    sede = models.ForeignKey('core.Sede', on_delete=models.PROTECT, null=True, blank=True)

    fecha = models.DateField()
    hora = models.TimeField(null=True, blank=True)                 # ya temporal
    tipo = models.CharField(max_length=3, choices=Tipo.choices)


    class Meta:
        db_table = "profesor_asistenciaprofesor"
        ordering = ["-fecha", "-hora"]

    def __str__(self):
        return f"{self.usuario} {self.get_tipo_display()} {self.fecha} {self.hora}"


    class AlumnoTemporal(models.Model):

        profesor = models.ForeignKey("usuarios.Usuario", null=True, blank=True, on_delete=models.SET_NULL)

        # Datos del postulante (copiados del form)
        nombres = models.CharField(max_length=120)
        apellidos = models.CharField(max_length=120)
        fecha_nacimiento = models.DateField(null=True, blank=True)
        rut = models.CharField(max_length=12)  # SIN unique aquí
        direccion = models.CharField(max_length=200, blank=True, default="")
        comuna = models.CharField(max_length=80, blank=True, default="")
        telefono = models.CharField(max_length=30, blank=True, default="")
        email = models.EmailField(null=True, blank=True)

        n_emergencia = models.CharField(max_length=30, blank=True, default="")
        prevision = models.CharField(max_length=30, blank=True, default="")

        apoderado_nombre = models.CharField(max_length=120, blank=True, default="")
        apoderado_telefono = models.CharField(max_length=30, blank=True, default="")
        apoderado_email = models.EmailField(null=True, blank=True)
        apoderado_fecha_nacimiento = models.DateField(null=True, blank=True)
        apoderado_rut = models.CharField(max_length=12, blank=True, default="")

        curso = models.ForeignKey("core.Curso", null=True, blank=True, on_delete=models.SET_NULL)


        motivacion_beca = models.TextField(blank=True, default="")

        creado = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ["-creado"]

        def __str__(self):
            return f"{self.nombres} {self.apellidos} ({self.rut})"
