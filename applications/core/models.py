# applications/core/models.py
from django.db import models
from django.conf import settings
from datetime import date
from django.utils.timezone import localdate
from django.core.exceptions import ValidationError
from django.utils import timezone

Usuario = settings.AUTH_USER_MODEL


class Sede(models.Model):
    nombre = models.CharField(max_length=200)
    comuna = models.CharField(max_length=120, blank=True)
    direccion = models.CharField(max_length=240, blank=True)

    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    radio_metros = models.PositiveIntegerField(default=150)  # radio de validación

    capacidad = models.PositiveIntegerField(default=0, blank=True)
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)

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

    dirigido_a = models.CharField(
        max_length=50,
        choices=[
            ("TODOS", "Todos"),
            ("PROFESORES", "Profesores"),
            ("ATLETAS", "Atletas"),
            ("APODERADOS", "Apoderados"),
            ("MULTIDISCIPLINARIO", "Equipo Multidisciplinario"),
            ("COORDINADORES", "Coordinadores"),
            ("ADMINISTRADORES", "Administradores"),
        ],
        default="TODOS",
    )

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.titulo} ({self.get_dirigido_a_display()})"


class Curso(models.Model):
    class Programa(models.TextChoices):
        FORMATIVO = "FORM", "Formativo"
        ALTO_REND = "ALTO", "Alto rendimiento"

    class Estado(models.TextChoices):
        BORRADOR = "BOR", "Borrador"
        PUBLICADO = "PUB", "Publicado"
        CERRADAS = "CER", "Inscripciones cerradas"
        ARCHIVADO = "ARC", "Archivado"

    # -------- Identificación --------
    nombre = models.CharField(max_length=120)
    programa = models.CharField(max_length=5, choices=Programa.choices, default=Programa.FORMATIVO)
    disciplina = models.ForeignKey("core.Deporte", on_delete=models.PROTECT)
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
    categoria = models.CharField(max_length=80, blank=True)
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT)

    # -------- Calendario --------
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)

    # -------- Cupos e inscripciones --------
    cupos = models.PositiveIntegerField(default=20)
    cupos_espera = models.PositiveIntegerField(default=0, help_text="Opcional: cupos de lista de espera")
    permitir_inscripcion_rapida = models.BooleanField(
        default=False,
        help_text="Permitir inscripción rápida del profesor en 1ra clase",
    )

    # -------- Estado --------
    publicado = models.BooleanField(default=False)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.BORRADOR)

    # -------- Compatibilidad (antiguos) --------
    horario = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="(Deprecado) Ej: Lun y Mié 18:00-19:30. Usar horarios estructurados.",
    )
    lista_espera = models.BooleanField(
        default=True,
        help_text="(Deprecado) Usa 'cupos_espera' en su lugar.",
    )

    # meta
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} - {self.get_programa_display()} - {self.disciplina}"

    # >>> helper para mostrar horarios en las tablas
    def horarios_str(self) -> str:
        qs = self.horarios.all().order_by("dia", "hora_inicio")
        if not qs.exists():
            return self.horario or "—"
        return " · ".join(
            f"{h.get_dia_display()} {h.hora_inicio:%H:%M}-{h.hora_fin:%H:%M}"
            for h in qs
        )

    @property
    def cupos_ocupados(self):
        # usa el reverse correcto de InscripcionCurso
        return self.inscripciones_curso.filter(estado="ACTIVA").count()

    @property
    def cupos_disponibles(self):
        if self.cupos is None:
            return None
        return max(int(self.cupos) - self.cupos_ocupados, 0)


class CursoHorario(models.Model):
    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="horarios")
    dia = models.IntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        ordering = ["dia", "hora_inicio"]

    def __str__(self):
        return f"{self.curso.nombre}: {self.get_dia_display()} {self.hora_inicio}-{self.hora_fin}"


# =========================================================
#                INSCRIPCIONES A CURSOS (NUEVO)
# =========================================================
class InscripcionCurso(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        CANCELADA = "CANCELADA", "Cancelada"

    # related_name únicos para no chocar con atleta.Inscripcion
    estudiante = models.ForeignKey(
        "Estudiante",
        on_delete=models.CASCADE,
        related_name="inscripciones_cursos",
    )
    curso = models.ForeignKey(
        "Curso",
        on_delete=models.CASCADE,
        related_name="inscripciones_curso",
    )
    fecha_inscripcion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVA)

    class Meta:
        unique_together = [("estudiante", "curso")]
        indexes = [
            models.Index(fields=["estudiante", "estado"]),
            models.Index(fields=["curso", "estado"]),
        ]

    def __str__(self):
        return f"{self.estudiante} -> {self.curso} ({self.estado})"

    # --------- Reglas de negocio ----------
    def clean(self):
        # 1) Curso debe estar publicado/abierto
        if hasattr(self.curso, "publicado") and not self.curso.publicado:
            raise ValidationError("El curso no está publicado.")
        if hasattr(self.curso, "estado") and str(self.curso.estado).upper() in {"CERRADO", "INACTIVO"}:
            raise ValidationError("El curso no está abierto.")

        # 2) Cupos disponibles (solo inscripciones activas)
        activos = InscripcionCurso.objects.filter(curso=self.curso, estado=self.Estado.ACTIVA).count()
        if hasattr(self.curso, "cupos") and self.curso.cupos is not None:
            if activos >= int(self.curso.cupos):
                raise ValidationError("No hay cupos disponibles en este curso.")

        # 3) Choques de horario usando related_name="horarios"
        mis_otros = (
            InscripcionCurso.objects
            .filter(estudiante=self.estudiante, estado=self.Estado.ACTIVA)
            .exclude(pk=self.pk)
            .select_related("curso")
        )

        horarios_nuevos = list(self.curso.horarios.all().values("dia", "hora_inicio", "hora_fin"))
        for ins in mis_otros:
            horarios_existentes = list(ins.curso.horarios.all().values("dia", "hora_inicio", "hora_fin"))
            for hN in horarios_nuevos:
                for hE in horarios_existentes:
                    if hN["dia"] == hE["dia"]:
                        if hN["hora_inicio"] < hE["hora_fin"] and hN["hora_fin"] > hE["hora_inicio"]:
                            raise ValidationError(
                                f"Choque de horario con el curso '{ins.curso.nombre}' el día {hN['dia']}."
                            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Planificacion(models.Model):
    curso = models.ForeignKey(
        'core.Curso', on_delete=models.CASCADE,
        related_name='planificaciones', null=True, blank=True
    )
    semana = models.DateField(null=True, blank=True, help_text='Fecha del lunes de la semana')
    semana_iso = models.CharField(max_length=10, blank=True, default="", db_index=True)
    archivo = models.FileField(upload_to="planificaciones/", blank=True, null=True)
    comentarios = models.TextField(blank=True, null=True)
    publica = models.BooleanField(default=False)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-semana", "-creado"]
        indexes = [
            models.Index(fields=["curso", "semana"]),
            models.Index(fields=["semana_iso"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["curso", "semana"], name="uniq_plan_curso_semana"),
        ]

    def __str__(self):
        return f"{self.curso} · semana {self.semana}"

    def set_semana_iso(self):
        if self.semana:
            iso_year, iso_week, _ = self.semana.isocalendar()
            self.semana_iso = f"{iso_year}-W{int(iso_week):02d}"

    def save(self, *args, **kwargs):
        self.set_semana_iso()
        super().save(*args, **kwargs)


class PlanificacionVersion(models.Model):
    planificacion = models.ForeignKey(Planificacion, on_delete=models.CASCADE, related_name="versiones")
    archivo = models.FileField(upload_to="planificaciones/versiones/%Y/%m/")
    creado = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Versión {self.id} de {self.planificacion}"


class AsistenciaClase(models.Model):
    curso_id = models.IntegerField()
    fecha = models.DateField()
    profesor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)


class AsistenciaAlumno(models.Model):
    asistencia = models.ForeignKey(AsistenciaClase, on_delete=models.CASCADE, related_name="alumnos")
    estudiante_id = models.IntegerField()
    presente = models.BooleanField(default=False)
    justificado = models.BooleanField(default=False)


class Estudiante(models.Model):
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    curso = models.ForeignKey("core.Curso", on_delete=models.SET_NULL, blank=True, null=True)
    activo = models.BooleanField(default=True)

    direccion = models.CharField(max_length=150, blank=True, null=True)
    comuna = models.CharField(max_length=80, blank=True, null=True)
    edad = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)

    n_emergencia = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Número de emergencia"
    )

    PREVISION_CHOICES = [
        ("FONASA", "Fonasa"),
        ("ISAPRE", "Isapre"),
        ("NINGUNA", "Ninguna"),
    ]
    prevision = models.CharField(
        max_length=20,
        choices=PREVISION_CHOICES,
        default="NINGUNA",
        verbose_name="Previsión de salud"
    )

    apoderado_nombre = models.CharField(max_length=200, blank=True, default="")
    apoderado_telefono = models.CharField(max_length=30, blank=True, default="")
    apoderado_rut = models.CharField(max_length=12, blank=True, default="")

    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True, default="")
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)
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
        # sugerencias suaves (no bloqueamos)
        if self.edad is not None and self.edad < 18:
            if not self.apoderado_nombre or not self.apoderado_telefono:
                pass
        if self.pertenece_organizacion and not self.club_nombre:
            pass
        super().save(*args, **kwargs)
