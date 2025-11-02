# applications/core/models.py
from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group  # grupos opcionales (mismo nombre que el código)
from datetime import date
from django.utils import timezone  # para defaults y now()

Usuario = settings.AUTH_USER_MODEL

# ====== Códigos de audiencia por tipo de usuario ======
# (PROF = Profesor, PMUL = Equipo Multi, ATLE = Alumno/Atleta, APOD = Apoderado)
AUDIENCIA_CODIGOS = ["PROF", "PMUL", "ATLE", "APOD"]


# ===================== SEDES / DEPORTES =====================
class Sede(models.Model):
    nombre = models.CharField(max_length=200)
    comuna = models.CharField(max_length=120, blank=True)
    direccion = models.CharField(max_length=240, blank=True)

    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    radio_metros = models.PositiveIntegerField(default=150)  # radio de validación (geofencing)

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


# ===================== NOTICIAS (portada) =====================
class Noticia(models.Model):
    titulo = models.CharField(max_length=180)
    bajada = models.CharField(max_length=280, blank=True)          # subtítulo/resumen corto
    cuerpo = models.TextField(blank=True)                           # texto largo (opcional)
    imagen = models.ImageField(upload_to="noticias/", blank=True, null=True)
    publicada = models.BooleanField(default=True)
    publicada_en = models.DateTimeField(null=True, blank=True)

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-publicada_en", "-creado"]

    def __str__(self):
        return self.titulo


# ===================== COMUNICADOS =====================
class ComunicadoQuerySet(models.QuerySet):
    def for_user(self, user):
        """
        Visibilidad:
        - is_superuser, ADMIN y COORD ven todo.
        - Resto: ven si su tipo_usuario (p.ej. 'PROF') está en audiencia_codigos
          o si pertenece a un Group con el mismo nombre del código (PROF/PMUL/ATLE/APOD).
        """
        tu = getattr(user, "tipo_usuario", None)
        if getattr(user, "is_superuser", False) or tu in ("ADMIN", "COORD"):
            return self

        q_tu = models.Q(audiencia_codigos__icontains=tu) if tu else models.Q(pk__in=[])
        q_grp = models.Q(audiencia_roles__in=Group.objects.filter(user=user, name__in=AUDIENCIA_CODIGOS))

        return self.filter(q_tu | q_grp).distinct()


class Comunicado(models.Model):
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    # CSV de códigos de audiencia seleccionados: p.ej. "PROF,ATLE"
    audiencia_codigos = models.CharField(max_length=100, default="", blank=True)

    # Soporte opcional por grupos con el MISMO nombre del código (PROF/PMUL/ATLE/APOD)
    audiencia_roles = models.ManyToManyField(
        Group, blank=True, related_name="comunicados_dirigidos"
    )

    objects = ComunicadoQuerySet.as_manager()

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo

    # Helpers de audiencia
    def set_audiencia_codigos(self, codigos):
        cods = [c for c in (codigos or []) if c in AUDIENCIA_CODIGOS]
        self.audiencia_codigos = ",".join(sorted(set(cods)))

    def get_audiencia_codigos(self):
        if not (self.audiencia_codigos or "").strip():
            return []
        return [c for c in self.audiencia_codigos.split(",") if c]

    def visible_para(self, user) -> bool:
        tu = getattr(user, "tipo_usuario", None)
        if getattr(user, "is_superuser", False) or tu in ("ADMIN", "COORD"):
            return True
        if tu and tu in self.get_audiencia_codigos():
            return True
        return self.audiencia_roles.filter(user=user, name__in=AUDIENCIA_CODIGOS).exists()


# ===================== CURSOS =====================
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

    # helper para mostrar horarios en listados
    def horarios_str(self) -> str:
        qs = self.horarios.all().order_by("dia", "hora_inicio")
        if not qs.exists():
            return self.horario or "—"
        return " · ".join(
            f"{h.get_dia_display()} {h.hora_inicio:%H:%M}-{h.hora_fin:%H:%M}"
            for h in qs
        )


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


# ===================== PLANIFICACIONES =====================
class Planificacion(models.Model):
    curso = models.ForeignKey(
        "core.Curso",
        on_delete=models.CASCADE,
        related_name="planificaciones",
        null=True,
        blank=True,
    )
    semana = models.DateField(null=True, blank=True, help_text="Fecha del lunes de la semana")
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
        # aseguramos semana_iso cada vez
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


# ===================== ASISTENCIAS (placeholders) =====================
class AsistenciaClase(models.Model):
    # placeholder hasta integrar con tus clases reales
    curso_id = models.IntegerField()
    fecha = models.DateField()
    profesor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)


class AsistenciaAlumno(models.Model):
    asistencia = models.ForeignKey(AsistenciaClase, on_delete=models.CASCADE, related_name="alumnos")
    estudiante_id = models.IntegerField()
    presente = models.BooleanField(default=False)
    justificado = models.BooleanField(default=False)


# ===================== ESTUDIANTE =====================
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

    # metadatos
    creado = models.DateTimeField(default=timezone.now, null=True, blank=True)
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
