from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ADMIN='ADMIN','Administrador'
        COORD='COORD','Coordinador'
        PROF='PROF','Profesor/Entrenador'
        ATLE='ATLE','Atleta'
        APOD='APOD','Apoderado'
        PROF_MULT='PMUL','Profesional Multidisciplinario'
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    tipo_usuario = models.CharField(max_length=6, choices=Tipo.choices, default=Tipo.ATLE)

    def __str__(self):
        return f"{self.username} ({self.get_tipo_usuario_display()})"


class Coordinador(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'tipo_usuario': Usuario.Tipo.COORD})
    area_responsabilidad = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"Coord: {self.usuario}"


class Profesor(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'tipo_usuario': Usuario.Tipo.PROF})
    especialidad = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Prof: {self.usuario}"


class ProfesionalMulti(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'tipo_usuario': Usuario.Tipo.PROF_MULT})
    especialidad = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.especialidad}: {self.usuario}"


class Apoderado(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'tipo_usuario': Usuario.Tipo.APOD})
    contacto_emergencia = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Apoderado: {self.usuario}"
