# applications/atleta/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

Usuario = settings.AUTH_USER_MODEL

TIPO_ATLETA = [
    ("AR", "Alto Rendimiento"),
    ("FD", "Formación Deportiva"),
]

class Atleta(models.Model):
    """Perfil mínimo de atleta asociado a un Usuario(tipo ATLE)."""
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="perfil_atleta")
    rut = models.CharField(max_length=12, unique=True)
    tipo_atleta = models.CharField(max_length=2, choices=TIPO_ATLETA, default="FD")
    faltas_consecutivas = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} · {self.rut}"

class Inscripcion(models.Model):
    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name="inscripciones")
    fecha = models.DateField(default=timezone.now)
    deporte = models.CharField(max_length=100)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.atleta} · {self.deporte}"

class Clase(models.Model):
    sede_deporte = models.CharField(max_length=120)
    profesor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="clases_dictadas")
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tema = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.sede_deporte} · {self.fecha:%d/%m} {self.hora_inicio}-{self.hora_fin}"

class AsistenciaProfesor(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="asistencias_profesor")
    profesor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="asistencias_prof")
    presente = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

class AsistenciaAtleta(models.Model):
    clase = models.ForeignKey("atleta.Clase", on_delete=models.CASCADE, related_name="asistencias")
    atleta = models.ForeignKey("atleta.Atleta", null=True, blank=True, on_delete=models.SET_NULL)
    presente = models.BooleanField(default=False)
    justificada = models.BooleanField(default=False)          # 👈 cuenta como NO falta
    observaciones = models.CharField(max_length=250, blank=True, default="")

    # Invitado/sobre-cupo (cuando no está inscrito)
    invitado_nombre = models.CharField(max_length=120, blank=True, default="")
    invitado_rut = models.CharField(max_length=12, blank=True, default="")
    invitado_contacto = models.CharField(max_length=40, blank=True, default="")
    sobre_cupo = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        etiqueta = self.atleta or self.invitado_nombre or "—"
        return f"{self.clase} · {etiqueta}"
