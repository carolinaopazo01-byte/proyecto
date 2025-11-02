from django.db import models
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
        PMUL  = "PMUL",  "Profesional Multidisciplinario"

    # ---- Sub-rol SOLO para Equipo Multidisciplinario
    class EquipoRol(models.TextChoices):
        KINE  = "KINE", "Equipo Multidisciplinario - Kinesiólogo(a)"
        PSICO = "PSIC", "Equipo Multidisciplinario - Psicólogo(a)"
        NUTRI = "NUTR", "Equipo Multidisciplinario - Nutricionista"
        TENS  = "TENS", "Equipo Multidisciplinario - TENS"

    # --- Campos propios del programa
    # Guarda el RUT con puntos y guion (ej: 12.345.678-5). max_length=12 alcanza.
    rut = models.CharField(max_length=12, unique=True, db_index=True)
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
        # Evita fallar si cambias choices: usa value si no hay display
        try:
            rol = self.get_tipo_usuario_display()
        except Exception:
            rol = self.tipo_usuario or "—"
        return f"{self.rut} ({rol})"

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        # Reglas de sub-rol
        if self.tipo_usuario == self.Tipo.PMUL and not self.equipo_rol:
            raise ValidationError({"equipo_rol": "Selecciona el sub-rol del Equipo Multidisciplinario."})
        if self.tipo_usuario != self.Tipo.PMUL:
            self.equipo_rol = None

    # Normaliza antes de guardar por si llega por otra vía distinta al ModelForm
    def save(self, *args, **kwargs):
        from applications.usuarios.utils import normalizar_rut, formatear_rut
        if self.rut:
            # Asegura formato consistente "12.345.678-5"
            nr = normalizar_rut(self.rut)        # "12345678-5"
            self.rut = formatear_rut(nr)         # "12.345.678-5"
        return super().save(*args, **kwargs)

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
