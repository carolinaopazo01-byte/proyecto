from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.models import AbstractUser

# ------------------------------------------------------------------
# 1) Roles (opcional, por compatibilidad)
# ------------------------------------------------------------------
class Roles:
    ADMIN = "ADMIN"   # Administrador
    COORD = "COORD"   # Coordinador
    PROF  = "PROF"    # Profesor/Entrenador
    ATLE  = "ATLE"    # Atleta
    APOD  = "APOD"    # Apoderado
    PMUL  = "PMUL"    # Profesional Multidisciplinario (Equipo)

# ------------------------------------------------------------------
# 2) Usuario (custom)
# ------------------------------------------------------------------
class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        COORD = "COORD", "Coordinador"
        PROF  = "PROF",  "Profesor/Entrenador"
        ATLE  = "ATLE",  "Atleta"
        APOD  = "APOD",  "Apoderado"
        PMUL  = "PMUL",  "Profesional Multidisciplinario"  # Equipo multidisciplinario

    # ---- Sub-rol SOLO para Equipo Multidisciplinario
    class EquipoRol(models.TextChoices):
        KINE  = "KINE", "Equipo Multidisciplinario - Kinesiólogo(a)"
        PSICO = "PSIC", "Equipo Multidisciplinario - Psicólogo(a)"
        NUTRI = "NUTR", "Equipo Multidisciplinario - Nutricionista"
        TENS  = "TENS", "Equipo Multidisciplinario - TENS"

    # --- Campos propios del programa
    rut = models.CharField(max_length=12, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    tipo_usuario = models.CharField(max_length=5, choices=Tipo.choices, default=Tipo.ATLE)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    # Sub-rol (opcional, solo obligatorio si tipo = PMUL)
    equipo_rol = models.CharField(
        max_length=4,
        choices=EquipoRol.choices,
        blank=True,
        null=True,
        help_text="Solo para usuarios del Equipo Multidisciplinario."
    )

    # Autenticación por RUT
    USERNAME_FIELD = "rut"
    REQUIRED_FIELDS = ["username", "email"]

    def __str__(self):
        return f"{self.rut} ({self.get_tipo_usuario_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.tipo_usuario == self.Tipo.PMUL and not self.equipo_rol:
            raise ValidationError({"equipo_rol": "Selecciona el sub-rol del Equipo Multidisciplinario."})
        if self.tipo_usuario != self.Tipo.PMUL:
            self.equipo_rol = None

# ------------------------------------------------------------------
# 3) Modelos vinculados
# ------------------------------------------------------------------
class Coordinador(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={"tipo_usuario": Usuario.Tipo.COORD},
    )
    area_responsabilidad = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"Coord: {self.usuario}"

class Profesor(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={"tipo_usuario": Usuario.Tipo.PROF},
    )
    especialidad = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Prof: {self.usuario}"

class ProfesionalMulti(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={"tipo_usuario": Usuario.Tipo.PMUL},
    )
    especialidad = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.especialidad}: {self.usuario}"

class Apoderado(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        limit_choices_to={"tipo_usuario": Usuario.Tipo.APOD},
    )
    contacto_emergencia = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Apoderado: {self.usuario}"