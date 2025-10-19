# applications/core/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date
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
    # --- EXISTENTES (mantén los tuyos) ---
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    curso = models.ForeignKey('core.Curso', on_delete=models.SET_NULL, blank=True, null=True)
    activo = models.BooleanField(default=True)

    # --- NUEVOS: Identificación del/la atleta ---
    direccion = models.CharField(max_length=200, blank=True, default="")
    comuna = models.CharField(max_length=80, blank=True, default="")

    # Edad persistida (se calcula en save)
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)

    # --- NUEVOS: Tutor (si es menor de edad) ---
    apoderado_nombre = models.CharField(max_length=200, blank=True, default="")
    apoderado_telefono = models.CharField(max_length=30, blank=True, default="")

    # --- NUEVOS: Información deportiva ---
    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True, default="")
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)
    categoria_competida = models.CharField(max_length=80, blank=True, default="")
    puntaje_o_logro = models.CharField(max_length=120, blank=True, default="")

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.rut})"

    def _calc_edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        e = hoy.year - self.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
        return max(e, 0)

    def save(self, *args, **kwargs):
        self.edad = self._calc_edad()
        # Validaciones mínimas de negocio (opcional; puedes mover a forms.clean())
        if self.edad is not None and self.edad < 18:
            # sugerimos apoderado para menores de edad
            if not self.apoderado_nombre or not self.apoderado_telefono:
                # No levantamos excepción dura para no romper creación rápida;
                # si prefieres estricto: raise ValueError("Para menores...")
                pass
        if self.pertenece_organizacion and not self.club_nombre:
            # idem comentario anterior
            pass
        super().save(*args, **kwargs)