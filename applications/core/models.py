from django.db import models
from django.conf import settings
from django.db import models

Usuario = settings.AUTH_USER_MODEL

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
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo

class Planificacion(models.Model):
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mes = models.DateField(help_text="Usa el primer día del mes (ej: 2025-10-01)")
    archivo = models.FileField(upload_to="planificaciones/")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

class AsistenciaClase(models.Model):
    curso_id = models.IntegerField()  # placeholder hasta que tengas modelo Curso
    fecha = models.DateField()
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

class AsistenciaAlumno(models.Model):
    asistencia = models.ForeignKey(AsistenciaClase, on_delete=models.CASCADE, related_name="alumnos")
    estudiante_id = models.IntegerField()  # placeholder hasta modelo Estudiante
    presente = models.BooleanField(default=False)
    justificado = models.BooleanField(default=False)

class Curso(models.Model):
    class Programa(models.TextChoices):
        FORMATIVO = "FORM", "Formativo"
        ALTO_REND = "ALTO", "Alto rendimiento"

    nombre = models.CharField(max_length=120)
    programa = models.CharField(max_length=5, choices=Programa.choices, default=Programa.FORMATIVO)
    disciplina = models.ForeignKey("core.Deporte", on_delete=models.PROTECT)
    categoria = models.CharField(max_length=80, blank=True)  # ej: Sub-14, Adulto, etc.
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, limit_choices_to={"tipo_usuario": "PROF"})
    horario = models.CharField(max_length=120, help_text="Ej: Lun y Mié 18:00-19:30")
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT)
    cupos = models.PositiveIntegerField(default=20)
    publicado = models.BooleanField(default=False)  # RF: publicación del curso
    lista_espera = models.BooleanField(default=True)  # RF: habilitar lista de espera

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} - {self.get_programa_display()} - {self.disciplina}"

    # --- ESTUDIANTE ---


from django.db import models  # ya lo tienes arriba; si está, no repitas


class Estudiante(models.Model):
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)

    apoderado_nombre = models.CharField(max_length=120, blank=True)
    apoderado_telefono = models.CharField(max_length=20, blank=True)

    # referencia opcional a Curso (si tu modelo Curso existe)
    curso = models.ForeignKey("Curso", null=True, blank=True, on_delete=models.SET_NULL)

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres} ({self.rut})"
