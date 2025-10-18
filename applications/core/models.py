# applications/core/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime

# Para FKs al usuario
Usuario = settings.AUTH_USER_MODEL


# ===================== SEDES / DEPORTES =====================
class Sede(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    capacidad = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nombre


class Deporte(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=100, blank=True)
    equipamiento = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class SedeDeporte(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name="disciplinas")
    deporte = models.ForeignKey(Deporte, on_delete=models.CASCADE, related_name="sedes")
    fecha_inicio = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    cupos_max = models.PositiveIntegerField(default=30)

    class Meta:
        unique_together = ("sede", "deporte")

    def __str__(self):
        return f"{self.sede} - {self.deporte}"


# ===================== EVENTOS / COMUNICADOS =====================
class Evento(models.Model):
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=100, blank=True)
    fecha = models.DateField()
    lugar = models.CharField(max_length=150, blank=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.fecha})"


class Comunicado(models.Model):
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo


# ===================== PLANIFICACIÓN =====================
class Planificacion(models.Model):
    NIVEL_CHOICES = [
        ("baja", "Baja"),
        ("media", "Media"),
        ("alta", "Alta"),
    ]

    nombre = models.CharField(max_length=150, blank=True, default="")
    contenido = models.TextField(blank=True, default="")
    metodologia = models.TextField(blank=True, default="")
    duracion = models.DurationField(null=True, blank=True, default=datetime.timedelta())
    nivel_dificultad = models.CharField(
        max_length=10, choices=NIVEL_CHOICES, blank=True, default="media"
    )

    creado = models.DateTimeField(default=timezone.now)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.nombre or "(Sin nombre)"


# ===================== ASISTENCIAS (stubs) =====================
class AsistenciaClase(models.Model):
    curso_id = models.IntegerField()  # placeholder hasta que Curso tenga su flujo completo
    fecha = models.DateField()
    profesor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)


class AsistenciaAlumno(models.Model):
    asistencia = models.ForeignKey(AsistenciaClase, on_delete=models.CASCADE, related_name="alumnos")
    estudiante_id = models.IntegerField()  # placeholder hasta modelo Estudiante
    presente = models.BooleanField(default=False)
    justificado = models.BooleanField(default=False)


# ===================== CURSOS / ESTUDIANTES =====================
class Curso(models.Model):
    class Programa(models.TextChoices):
        FORMATIVO = "FORM", "Formativo"
        ALTO_REND = "ALTO", "Alto rendimiento"

    nombre = models.CharField(max_length=120)
    programa = models.CharField(max_length=5, choices=Programa.choices, default=Programa.FORMATIVO)
    disciplina = models.ForeignKey(Deporte, on_delete=models.PROTECT)
    categoria = models.CharField(max_length=80, blank=True)  # ej: Sub-14, Adulto, etc.
    profesor = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        limit_choices_to={"tipo_usuario": "PROF"},
        related_name="cursos_impartidos",
    )
    horario = models.CharField(max_length=120, help_text="Ej: Lun y Mié 18:00-19:30")
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT)
    cupos = models.PositiveIntegerField(default=20)
    publicado = models.BooleanField(default=False)
    lista_espera = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} - {self.get_programa_display()} - {self.disciplina}"


class Estudiante(models.Model):
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)

    apoderado_nombre = models.CharField(max_length=120, blank=True)
    apoderado_telefono = models.CharField(max_length=20, blank=True)

    curso = models.ForeignKey(Curso, null=True, blank=True, on_delete=models.SET_NULL)

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres} ({self.rut})"
