# applications/core/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date
import datetime

Usuario = settings.AUTH_USER_MODEL

class Sede(models.Model):
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=200)
    comuna = models.CharField(max_length=80, blank=True, default="Coquimbo")
    descripcion = models.TextField(blank=True)
    capacidad = models.PositiveIntegerField(null=True, blank=True)
    activa = models.BooleanField(default=True)

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

class Planificacion(models.Model):
    """
    Planificación por curso y semana. Guarda el archivo 'vigente' y
    quién lo subió. El campo 'semana' guarda la fecha del LUNES de esa semana.
    """
    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE, related_name="planificaciones")
    semana = models.DateField(help_text="Fecha del lunes de la semana")
    archivo = models.FileField(upload_to="planificaciones/%Y/%m/", null=True, blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("curso", "semana")  # 1 planificación vigente por curso/semana
        ordering = ["-semana", "-creado"]

    def __str__(self):
        return f"{self.curso} · semana {self.semana}"

class PlanificacionVersion(models.Model):
    """
    Historial de versiones para una Planificación (cada vez que se sube un nuevo archivo).
    """
    planificacion = models.ForeignKey(Planificacion, on_delete=models.CASCADE, related_name="versiones")
    archivo = models.FileField(upload_to="planificaciones/versiones/%Y/%m/")
    creado = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Versión {self.id} de {self.planificacion}"

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

class Curso(models.Model):
    class Programa(models.TextChoices):
        FORMATIVO = "FORM", "Formativo"
        ALTO_REND = "ALTO", "Alto rendimiento"

    class Estado(models.TextChoices):
        BORRADOR   = "BOR", "Borrador"
        PUBLICADO  = "PUB", "Publicado"
        CERRADAS   = "CER", "Inscripciones cerradas"
        ARCHIVADO  = "ARC", "Archivado"

    # -------- 1) Identificación --------
    nombre = models.CharField(max_length=120)
    programa = models.CharField(max_length=5, choices=Programa.choices, default=Programa.FORMATIVO)
    disciplina = models.ForeignKey('core.Deporte', on_delete=models.PROTECT)
    categoria = models.CharField(max_length=80, blank=True)  # ej: Sub-12, Adulto, Mixto
    sede = models.ForeignKey('core.Sede', on_delete=models.PROTECT)

    # -------- 2) Calendario --------
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)

    # -------- 3) Profesorado --------
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        limit_choices_to={"tipo_usuario": "PROF"},
        related_name="cursos_impartidos",
    )
    profesores_apoyo = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="cursos_apoyo",
        limit_choices_to={"tipo_usuario": "PROF"},
        help_text="Profesores de apoyo (opcional, múltiple)",
    )

    # -------- 4) Cupos e inscripciones --------
    cupos = models.PositiveIntegerField(default=20)
    cupos_espera = models.PositiveIntegerField(default=0, help_text="Opcional: cupos de lista de espera")
    permitir_inscripcion_rapida = models.BooleanField(
        default=False,
        help_text="Permitir inscripción rápida del profesor en 1ra clase"
    )

    # -------- 5) Visibilidad/Estado --------
    publicado = models.BooleanField(default=False)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.BORRADOR)

    # -------- Compatibilidad (antiguos) --------
    # Campo antiguo de horario en texto: lo dejamos pero ya NO se usa en el formulario nuevo.
    horario = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="(Deprecado) Ej: Lun y Mié 18:00-19:30. Usar horarios estructurados."
    )
    lista_espera = models.BooleanField(
        default=True,
        help_text="(Deprecado) Usa 'cupos_espera' en su lugar."
    )

    # Meta
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} - {self.get_programa_display()} - {self.disciplina}"


class CursoHorario(models.Model):
    class Dia(models.IntegerChoices):
        LUNES     = 0, "Lunes"
        MARTES    = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES    = 3, "Jueves"
        VIERNES   = 4, "Viernes"
        SABADO    = 5, "Sábado"
        DOMINGO   = 6, "Domingo"

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="horarios")
    dia = models.IntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        ordering = ["dia", "hora_inicio"]

    def __str__(self):
        return f"{self.curso.nombre}: {self.get_dia_display()} {self.hora_inicio}-{self.hora_fin}"

class Estudiante(models.Model):

    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    telefono  = models.CharField(max_length=20,  blank=True, null=True)  # si la usas
    curso = models.ForeignKey('core.Curso', on_delete=models.SET_NULL, blank=True, null=True)
    activo = models.BooleanField(default=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    comuna    = models.CharField(max_length=80,  blank=True, null=True)  # si la usas
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    apoderado_nombre = models.CharField(max_length=200, blank=True, default="")
    apoderado_telefono = models.CharField(max_length=30, blank=True, default="")
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