from django.db import models
from django.conf import settings
from django.utils import timezone
from applications.core.models import Estudiante

Usuario = settings.AUTH_USER_MODEL

# ----------------------------
# Catálogos de apoyo
# ----------------------------
ESPECIALIDADES = [
    ("NUT", "Nutricionista"),
    ("KIN", "Kinesiólogo/a"),
    ("TENS", "TENS"),
    ("COORD", "Coordinador/a"),
    ("APOYO", "Apoyo deportivo"),
    ("TSOC", "Trabajador/a social"),
    ("OTRA", "Otra"),
]

PISOS = [
    (1, "Primer piso"),
    (2, "Segundo piso"),
]


def piso_por_especialidad(code: str) -> int:
    """Determina automáticamente el piso según la especialidad."""
    if code in {"NUT", "KIN"}:
        return 1
    return 2


# ----------------------------
# Modelo de perfil profesional
# ----------------------------
class ProfesionalPerfil(models.Model):
    """Perfil para profesionales PMUL sin tocar tu modelo de usuario."""
    user = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="perfil_pmul")
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA")

    def piso_predeterminado(self) -> int:
        return piso_por_especialidad(self.especialidad)

    def __str__(self):
        return f"{self.user} · {self.get_especialidad_display()}"


# ----------------------------
# Modelo de citas
# ----------------------------
class Cita(models.Model):
    ESTADOS = [
        ("PEND", "Pendiente"),
        ("REAL", "Atendida"),
        ("REPROG", "Reprogramada"),
        ("CANC", "Cancelada"),
    ]

    paciente = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="citas")
    profesional = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="citas_pmul")
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA", editable=False)
    piso = models.PositiveSmallIntegerField(choices=PISOS, default=1, editable=False)
    estado = models.CharField(max_length=6, choices=ESTADOS, default="PEND")
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ["inicio"]

    def save(self, *args, **kwargs):
        try:
            esp = self.profesional.perfil_pmul.especialidad
        except Exception:
            esp = "OTRA"
        self.especialidad = esp
        self.piso = piso_por_especialidad(esp)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.paciente} · {self.inicio:%d/%m %H:%M}"


# ----------------------------
# Modelo de fichas clínicas
# ----------------------------
class FichaClinica(models.Model):
    ESTADOS_FICHA = [
        ("FIN", "Finalizada"),
        ("SEG", "En seguimiento"),
    ]

    paciente = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="fichas")
    profesional = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="fichas_pmul")
    fecha = models.DateField(auto_now_add=True)
    especialidad = models.CharField(max_length=5, choices=ESPECIALIDADES, default="OTRA", editable=False)
    motivo = models.CharField(max_length=200, blank=True)
    observaciones = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    estado = models.CharField(max_length=3, choices=ESTADOS_FICHA, default="FIN")

    # publicación por rol (visibilidad)
    publicar_profesor = models.BooleanField(default=False)
    publicar_coordinador = models.BooleanField(default=True)
    publicar_admin = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        try:
            esp = self.profesional.perfil_pmul.especialidad
        except Exception:
            esp = "OTRA"
        self.especialidad = esp
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ficha {self.paciente} {self.fecha:%d/%m/%Y}"


# ----------------------------
# Modelo de adjuntos
# ----------------------------
class FichaAdjunto(models.Model):
    ficha = models.ForeignKey(FichaClinica, on_delete=models.CASCADE, related_name="adjuntos")
    archivo = models.FileField(upload_to="fichas_adjuntos/")
    nombre = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nombre or self.archivo.name
