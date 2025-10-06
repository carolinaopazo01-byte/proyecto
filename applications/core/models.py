from django.db import models
from django.conf import settings

Usuario = settings.AUTH_USER_MODEL

class Sede(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    capacidad = models.IntegerField(default=0)

    def __str__(self):
        return self.nombre


class Deporte(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=100, blank=True)
    equipamiento = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class SedeDeporte(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='disciplinas')
    deporte = models.ForeignKey(Deporte, on_delete=models.CASCADE, related_name='sedes')
    fecha_inicio = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    cupos_max = models.PositiveIntegerField(default=30)

    class Meta:
        unique_together = ('sede', 'deporte')

    def __str__(self):
        return f"{self.sede} - {self.deporte}"


class Evento(models.Model):
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=100, blank=True)
    fecha = models.DateField()
    lugar = models.CharField(max_length=150, blank=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.fecha})"


class Comunicado(models.Model):
    titulo = models.CharField(max_length=150)
    contenido = models.TextField()
    creado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo
