from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.models import AbstractUser
# ------------------------------------------------------------------
# 1) Roles (y "shim" compatible con Usuario.Tipo.ADMIN, etc.)
# ------------------------------------------------------------------
class Roles:
    ADMIN = "ADMIN"   # Administrador
    COORD = "COORD"   # Coordinador
    PROF  = "PROF"    # Profesor/Entrenador
    ATLE  = "ATLE"    # Atleta
    APOD  = "APOD"    # Apoderado
    PMUL  = "PMUL"    # Profesional Multidisciplinario

# ------------------------------------------------------------------
# 2) Manager de Usuario
# ------------------------------------------------------------------
class UsuarioManager(BaseUserManager):
    def create_user(self, rut, password=None, **extra_fields):
        if not rut:
            raise ValueError("El usuario debe tener un RUT")
        rut = rut.replace(".", "").replace(" ", "").upper()
        if "-" not in rut and len(rut) > 1:
            rut = rut[:-1] + "-" + rut[-1]
        user = self.model(rut=rut, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, rut, password=None, **extra_fields):
        # Para compatibilidad si alguna vez usas createsuperuser
        extra_fields.setdefault("tipo_usuario", Roles.ADMIN)
        user = self.create_user(rut, password, **extra_fields)
        return user

# ------------------------------------------------------------------
# 3) Modelo Usuario simplificado
# ------------------------------------------------------------------
class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        COORD = "COORD", "Coordinador"
        PROF  = "PROF",  "Profesor/Entrenador"
        ATLE  = "ATLE",  "Atleta"
        APOD  = "APOD",  "Apoderado"
        PMUL  = "PMUL",  "Profesional Multidisciplinario"  # antes PROF_MULT

    # --- Campos propios del programa
    rut = models.CharField(max_length=12, unique=True, null=False, blank=False)
    telefono = models.CharField(max_length=20, blank=True)
    # ATENCIÓN: pon aquí el NOMBRE CORRECTO del campo (no “tipo_usuario1”)
    tipo_usuario = models.CharField(max_length=5, choices=Tipo.choices, default=Tipo.ATLE)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)  # ← añade esto
    # Vamos a autenticar por RUT:
    USERNAME_FIELD = "rut"
    REQUIRED_FIELDS = ["username", "email"]  # para que admin pueda crear usuarios

    def __str__(self):
        return f"{self.rut} ({self.get_tipo_usuario_display()})"

# ------------------------------------------------------------------
# 4) Modelos vinculados (sin usar TextChoices; limit_choices_to con strings)
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
