from datetime import date
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import Group  # para audiencia por grupos

Usuario = settings.AUTH_USER_MODEL


AUDIENCIA_CODIGOS = ["PROF", "PMUL", "ATLE", "APOD"]



class Sede(models.Model):
    nombre = models.CharField(max_length=200)
    comuna = models.CharField(max_length=120, blank=True)
    direccion = models.CharField(max_length=240, blank=True)
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    radio_metros = models.PositiveIntegerField(default=150)
    capacidad = models.PositiveIntegerField(null=True, blank=True, default=None)
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Deporte(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=100, blank=True)
    equipamiento = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class SedeDeporte(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name="disciplinas")
    deporte = models.ForeignKey(Deporte, on_delete=models.CASCADE, related_name="sedes")
    fecha_inicio = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    cupos_max = models.PositiveIntegerField(default=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sede", "deporte"], name="uniq_sede_deporte"),
        ]
        ordering = ["sede__nombre", "deporte__nombre"]

    def __str__(self):
        return f"{self.sede} - {self.deporte}"


class Evento(models.Model):
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=100, blank=True)
    fecha = models.DateField()
    lugar = models.CharField(max_length=150, blank=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.fecha})"



class Noticia(models.Model):
    titulo = models.CharField(max_length=180)
    bajada = models.CharField(max_length=280, blank=True)
    cuerpo = models.TextField(blank=True)
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



from django.db import models
from django.conf import settings
from django.contrib.auth.models import Group


# ==========================================
# Comunicado (audiencias y manager)
# ==========================================

class Audiencia(models.TextChoices):
    PROF = "PROF", "Profesor"
    ATAP = "ATAP", "Atleta/Apoderado"
    PMUL = "PMUL", "Profesional Multidisciplinario"
    PUBL = "PUBL", "Público"  # visible sin iniciar sesión

AUDIENCIA_CODIGOS = tuple(a.value for a in Audiencia)  # ("PROF","ATAP","PMUL","PUBL")


def _csv_code_regex(code: str) -> str:


    return rf'(^|,){code}(,|$)'


class ComunicadoQuerySet(models.QuerySet):
    def publics(self):

        return self.filter(audiencia_codigos__regex=_csv_code_regex(Audiencia.PUBL))

    def for_user(self, user):

        tu = (getattr(user, "tipo_usuario", None) or "").upper()


        if getattr(user, "is_superuser", False) or tu in ("ADMIN", "COORD"):
            return self


        q_pub = models.Q(audiencia_codigos__regex=_csv_code_regex(Audiencia.PUBL))

        # Mapear tipo_usuario -> código de audiencia
        # ATLE o APOD => ATAP (Atleta/Apoderado)
        map_tu = {
            "PROF": Audiencia.PROF,
            "ATLE": Audiencia.ATAP,
            "APOD": Audiencia.ATAP,
            "PMUL": Audiencia.PMUL,
        }
        code = map_tu.get(tu)
        q_tu = models.Q()
        if code:
            q_tu = models.Q(audiencia_codigos__regex=_csv_code_regex(code))


        try:
            grp_names = set(user.groups.values_list("name", flat=True))
        except Exception:
            grp_names = set()
        grp_names = [n for n in grp_names if n in AUDIENCIA_CODIGOS]

        q_grp = models.Q()
        if grp_names:
            q_grp = models.Q(audiencia_roles__name__in=grp_names)

        return self.filter(q_pub | q_tu | q_grp).distinct()


class Comunicado(models.Model):
    """Comunicados con control de audiencia por códigos CSV (PROF, ATAP, PMUL, PUBL)."""
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


    audiencia_codigos = models.CharField(max_length=60, default="", blank=True)


    audiencia_roles = models.ManyToManyField(
        Group, blank=True, related_name="comunicados_dirigidos"
    )

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    objects = ComunicadoQuerySet.as_manager()

    class Meta:
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["-creado"]),
        ]

    def __str__(self):
        return self.titulo


    def set_audiencia_codigos(self, codigos):

        valid = [c for c in (codigos or []) if c in AUDIENCIA_CODIGOS]
        self.audiencia_codigos = ",".join(sorted(set(valid)))

    def get_audiencia_codigos(self):

        txt = (self.audiencia_codigos or "").strip()
        if not txt:
            return []
        return [c for c in txt.split(",") if c]

    @property
    def es_publico(self) -> bool:

        return Audiencia.PUBL in self.get_audiencia_codigos()



class Curso(models.Model):
    class Programa(models.TextChoices):
        FORMATIVO = "FORM", "Formativo"
        ALTO_REND = "ALTO", "Alto rendimiento"

    class Estado(models.TextChoices):
        BORRADOR = "BOR", "Borrador"
        PUBLICADO = "PUB", "Publicado"
        CERRADAS = "CER", "Inscripciones cerradas"
        ARCHIVADO = "ARC", "Archivado"

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
    )
    categoria = models.CharField(max_length=80, blank=True)
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)
    cupos = models.PositiveIntegerField(default=20)
    cupos_espera = models.PositiveIntegerField(default=0)
    permitir_inscripcion_rapida = models.BooleanField(default=False)
    publicado = models.BooleanField(default=False)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.BORRADOR)
    horario = models.CharField(max_length=120, blank=True, default="")
    lista_espera = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} - {self.get_programa_display()} - {self.disciplina}"

    def horarios_str(self):
        qs = self.horarios.all().order_by("dia", "hora_inicio")
        if not qs.exists():
            return self.horario or "—"
        return " · ".join(f"{h.get_dia_display()} {h.hora_inicio:%H:%M}-{h.hora_fin:%H:%M}" for h in qs)

from django.core.exceptions import ValidationError

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


    def clean(self):
        from .models import CursoHorario  # import local
        profesor = getattr(self.curso, "profesor", None)
        sede = getattr(self.curso, "sede", None)

        # No seguimos si el curso no tiene aún profesor o sede
        if not (profesor and sede):
            return

        conflictos = []

        # Choques con otros cursos del mismo profesor
        choques_prof = CursoHorario.objects.filter(
            curso__profesor=profesor,
            dia=self.dia,
            hora_inicio__lt=self.hora_fin,
            hora_fin__gt=self.hora_inicio,
        ).exclude(pk=self.pk)
        if choques_prof.exists():
            conflictos.append(
                f"El profesor {profesor} ya tiene otro curso el "
                f"{self.get_dia_display()} entre {self.hora_inicio} y {self.hora_fin}."
            )

        # Choques con otros cursos de la misma sede
        choques_sede = CursoHorario.objects.filter(
            curso__sede=sede,
            dia=self.dia,
            hora_inicio__lt=self.hora_fin,
            hora_fin__gt=self.hora_inicio,
        ).exclude(pk=self.pk)
        if choques_sede.exists():
            conflictos.append(
                f"La sede {sede} ya tiene otro curso el "
                f"{self.get_dia_display()} entre {self.hora_inicio} y {self.hora_fin}."
            )

        if conflictos:
            raise ValidationError(conflictos)


# ===================== PLANIFICACIONES =====================
class Planificacion(models.Model):
    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE, related_name="planificaciones", null=True, blank=True)
    semana = models.DateField(null=True, blank=True)
    semana_iso = models.CharField(max_length=10, blank=True, default="", db_index=True)
    archivo = models.FileField(upload_to="planificaciones/", blank=True, null=True)
    comentarios = models.TextField(blank=True, null=True)
    publica = models.BooleanField(default=False)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-semana", "-creado"]

    def __str__(self):
        return f"{self.curso} · semana {self.semana}"

    def save(self, *args, **kwargs):
        if self.semana:
            iso_year, iso_week, _ = self.semana.isocalendar()
            self.semana_iso = f"{iso_year}-W{int(iso_week):02d}"
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


# ===================== ASISTENCIAS =====================
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
    n_emergencia = models.CharField(max_length=30, blank=True, verbose_name="Número de emergencia")
    PREVISION_CHOICES = [("FONASA", "Fonasa"), ("ISAPRE", "Isapre"), ("NINGUNA", "Ninguna")]
    prevision = models.CharField(max_length=20, choices=PREVISION_CHOICES, default="NINGUNA", verbose_name="Previsión de salud")
    apoderado_nombre = models.CharField(max_length=200, blank=True, default="")
    apoderado_telefono = models.CharField(max_length=30, blank=True, default="")
    apoderado_rut = models.CharField(max_length=12, blank=True, default="")
    apoderado_email = models.EmailField(blank=True, null=True)
    apoderado_fecha_nacimiento = models.DateField(blank=True, null=True)
    pertenece_organizacion = models.BooleanField(default=False)
    club_nombre = models.CharField(max_length=120, blank=True, default="")
    logro_nacional = models.BooleanField(default=False)
    logro_internacional = models.BooleanField(default=False)
    creado = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modificado = models.DateTimeField(auto_now=True)
    categoria_competida = models.CharField(max_length=80, blank=True, default="")
    puntaje_o_logro = models.CharField(max_length=120, blank=True, default="")
    genero = models.CharField(max_length=1, choices=[("M", "Masculino"), ("F", "Femenino")], blank=True, null=True)

    class Meta:
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.rut})"

    def _calc_edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        e = hoy.year - self.fecha_nacimiento.year - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        return max(e, 0)

    def save(self, *args, **kwargs):
        self.edad = self._calc_edad()
        super().save(*args, **kwargs)


# ===================== POSTULACIONES =====================
class PostulacionEstudiante(models.Model):
    class Estado(models.TextChoices):
        NUEVA = "NEW", "Nueva"
        CONTACTADA = "CON", "Contactada"
        ACEPTADA = "ACE", "Aceptada"
        RECHAZADA = "REC", "Rechazada"

    periodo = models.ForeignKey("core.RegistroPeriodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="postulaciones")
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, default="")
    comuna = models.CharField(max_length=80, blank=True, default="")
    deporte_interes = models.ForeignKey("core.Deporte", on_delete=models.SET_NULL, null=True, blank=True)
    sede_interes = models.ForeignKey("core.Sede", on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.NUEVA, db_index=True)
    comentarios = models.TextField(blank=True, default="")
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)
    origen = models.CharField(max_length=60, blank=True, default="", help_text="Ej: web, feria, derivación")

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Postulación {self.rut} - {self.nombres} {self.apellidos}"


class RegistroPeriodo(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "PROG", "Programada"
        ABIERTA = "OPEN", "Abierta"
        CERRADA = "CLOSE", "Cerrada"

    nombre = models.CharField(max_length=120)
    inicio = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=5, choices=Estado.choices, default=Estado.PROGRAMADA, db_index=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

    @property
    def esta_en_rango(self):
        now = timezone.now()
        if self.inicio and now < self.inicio:
            return False
        if self.fin and now > self.fin:
            return False
        return True

    def abierta_para_publico(self):
        return self.activo and self.estado == self.Estado.ABIERTA and self.esta_en_rango


# ===================== ASISTENCIA CURSO =====================
class AsistenciaCurso(models.Model):
    class Estado(models.TextChoices):
        PEND = "PEND", "Pendiente"
        ENCU = "ENCU", "En curso"
        CERR = "CERR", "Cerrada"

    curso = models.ForeignKey("core.Curso", on_delete=models.CASCADE, related_name="asistencias")
    fecha = models.DateField()
    estado = models.CharField(max_length=4, choices=Estado.choices, default=Estado.PEND)
    inicio_real = models.TimeField(null=True, blank=True)
    fin_real = models.TimeField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = (("curso", "fecha"),)
        ordering = ("-fecha", "curso_id")

    def __str__(self):
        return f"Asistencia {self.curso} {self.fecha:%Y-%m-%d}"

    @property
    def resumen(self):
        agg = {"P": 0, "A": 0, "J": 0, "total": 0}
        for d in self.detalles.all():
            agg["total"] += 1
            agg[d.estado] = agg.get(d.estado, 0) + 1
        return agg
class AsistenciaCursoDetalle(models.Model):
    ESTADOS = (
        ("P", "Presente"),
        ("A", "Ausente"),
        ("J", "Justificado"),
    )
    asistencia = models.ForeignKey(AsistenciaCurso, on_delete=models.CASCADE, related_name="detalles")
    estudiante = models.ForeignKey("core.Estudiante", on_delete=models.CASCADE, related_name="asistencias_curso")
    estado = models.CharField(max_length=1, choices=ESTADOS, default="P")
    observaciones = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = (("asistencia", "estudiante"),)

    def __str__(self):
        return f"{self.estudiante} - {self.asistencia.fecha} ({self.estado})"
