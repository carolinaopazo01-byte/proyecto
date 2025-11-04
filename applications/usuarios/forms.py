# applications/usuarios/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

# Helpers centralizados
from .utils import normalizar_rut, formatear_rut

Usuario = get_user_model()  # respeta AUTH_USER_MODEL


# ---- Cálculo de dígito verificador -----------------------------------------
def _rut_calc_dv(numero: str) -> str:
    """
    Calcula el DV chileno para la parte numérica del RUT (sin puntos ni guion).
    """
    factores = [2, 3, 4, 5, 6, 7]
    s, i = 0, 0
    for d in reversed(numero):
        s += int(d) * factores[i]
        i = (i + 1) % len(factores)
    r = 11 - (s % 11)
    if r == 11:
        return "0"
    if r == 10:
        return "K"
    return str(r)


# =========================== CREATE =========================================
class UsuarioCreateForm(forms.ModelForm):
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=True,
        label="Fecha de nacimiento",
    )
    is_active = forms.BooleanField(initial=True, required=False, label="Activo")

    class Meta:
        model = Usuario
        fields = [
            "rut",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "fecha_nacimiento",
            "tipo_usuario",
            "equipo_rol",  # sub-rol (solo PMUL)
            "is_active",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "telefono": "Teléfono (ej: 9 99999999)",
            "tipo_usuario": "Rol",
            "equipo_rol": "Sub-rol (Equipo Multidisciplinario)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Importante: no requerido a nivel de campo (se valida condicionalmente en clean)
        if "equipo_rol" in self.fields:
            self.fields["equipo_rol"].required = False

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("tipo_usuario")
        subrol = cleaned.get("equipo_rol")

        # Sub-rol solo si PMUL
        if rol == Usuario.Tipo.PMUL and not subrol:
            self.add_error("equipo_rol", "Selecciona el sub-rol del Equipo Multidisciplinario.")
        if rol != Usuario.Tipo.PMUL:
            cleaned["equipo_rol"] = None  # fuerza vacío si no es PMUL

        return cleaned

    def clean_rut(self):
        """
        Acepta cualquier formato de entrada y valida DV con un parser robusto:
        - Toma SOLO dígitos y la ÚLTIMA letra (K/k) como DV.
        - La base queda como solo dígitos; ignora cualquier 'K' intermedia pegada por error.
        """
        rut_raw = (self.cleaned_data.get("rut") or "").strip()

        # 1) Quita TODO salvo dígitos y letras K/k
        tokens = [c for c in rut_raw if c.isdigit() or c.upper() == "K"]
        if len(tokens) < 2:
            raise DjangoValidationError("RUT inválido.")

        # 2) La ÚLTIMA es el DV; la base = dígitos del resto
        dv = tokens[-1].upper()
        base_digits = [c for c in tokens[:-1] if c.isdigit()]
        base = "".join(base_digits)

        if not base.isdigit() or len(base) < 6:
            raise DjangoValidationError("RUT inválido.")

        dv_ok = _rut_calc_dv(base)
        if dv != dv_ok:
            # Mensaje explícito con el DV correcto
            raise DjangoValidationError(f"Dígito verificador incorrecto. Debe ser “{dv_ok}”.")

        # 3) Normaliza y formatea
        rut_norm = f"{base}-{dv}"
        rut_fmt = formatear_rut(rut_norm)  # "12.345.678-9"

        # 4) Unicidad por RUT con formato final
        if Usuario.objects.filter(rut__iexact=rut_fmt).exists():
            raise DjangoValidationError("Ya existe un usuario con ese RUT.")

        return rut_fmt

    def save(self, commit=True):
        user = super().save(commit=False)

        # username plano (sin puntos ni guion) basado en el RUT ya formateado
        user.username = normalizar_rut(user.rut).replace("-", "")  # normalizar_rut -> "12345678-9"

        # Permisos por rol
        if user.tipo_usuario == Usuario.Tipo.ADMIN:
            user.is_staff = True
            user.is_superuser = True
        elif user.tipo_usuario == Usuario.Tipo.COORD:
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        # Password por fecha (DDMMAAAA) validada contra políticas
        fn = self.cleaned_data.get("fecha_nacimiento")
        if fn:
            pwd = f"{fn.day:02d}{fn.month:02d}{fn.year:04d}"
            try:
                validate_password(pwd, user=user)
            except DjangoValidationError as e:
                # Bloquea la creación si no cumple políticas (puedes cambiar por generación de temporal)
                raise DjangoValidationError(
                    {"fecha_nacimiento": ["La contraseña inicial no cumple la política."] + e.messages}
                )
            user.set_password(pwd)

        if commit:
            user.save()
        return user


# =========================== UPDATE =========================================
class UsuarioUpdateForm(forms.ModelForm):
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        label="Fecha de nacimiento",
    )

    class Meta:
        model = Usuario
        fields = [
            "rut",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "tipo_usuario",
            "equipo_rol",  # sub-rol (solo PMUL)
            "is_active",
            "fecha_nacimiento",
        ]
        widgets = {
            "rut": forms.TextInput(attrs={"readonly": "readonly"}),
        }
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "tipo_usuario": "Rol",
            "equipo_rol": "Sub-rol (Equipo Multidisciplinario)",
            "is_active": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Igual que en create: evitar que sea requerido a nivel de campo
        if "equipo_rol" in self.fields:
            self.fields["equipo_rol"].required = False

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("tipo_usuario")
        subrol = cleaned.get("equipo_rol")

        if rol == Usuario.Tipo.PMUL and not subrol:
            self.add_error("equipo_rol", "Selecciona el sub-rol del Equipo Multidisciplinario.")
        if rol != Usuario.Tipo.PMUL:
            cleaned["equipo_rol"] = None  # limpiar si cambió a otro rol

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)

        # Mantén username consistente (por si en algún momento permites editar RUT)
        user.username = normalizar_rut(user.rut).replace("-", "")

        # Permisos por rol
        if user.tipo_usuario == Usuario.Tipo.ADMIN:
            user.is_staff = True
            user.is_superuser = True
        elif user.tipo_usuario == Usuario.Tipo.COORD:
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        if commit:
            user.save()
        return user


# ====================== Cambio de contraseña ================================
class CambioPasswordForm(forms.Form):
    """
    Form para el template templates/atletas/cambiar_password.html
    Campos esperados: email, pwd_old, pwd1, pwd2
    """
    email = forms.EmailField(required=False, label="Correo electrónico")
    pwd_old = forms.CharField(widget=forms.PasswordInput, required=True, label="Contraseña actual")
    pwd1 = forms.CharField(widget=forms.PasswordInput, required=True, label="Nueva contraseña")
    pwd2 = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirmar nueva contraseña")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        if not (self.user and self.user.email):
            self.fields["email"].required = True

    def clean(self):
        cleaned = super().clean()
        user = self.user

        old = cleaned.get("pwd_old")
        new1 = cleaned.get("pwd1")
        new2 = cleaned.get("pwd2")

        # Verifica contraseña actual
        if old and not user.check_password(old):
            self.add_error("pwd_old", "Contraseña actual incorrecta.")

        # Confirmación
        if new1 and new2 and new1 != new2:
            self.add_error("pwd2", "Las contraseñas no coinciden.")

        # Políticas de Django
        if new1:
            try:
                validate_password(new1, user=user)
            except DjangoValidationError as e:
                self.add_error("pwd1", e)

        return cleaned

    def save(self):
        user = self.user
        email = self.cleaned_data.get("email")
        if email and not user.email:
            user.email = email
        user.set_password(self.cleaned_data["pwd1"])
        user.save()
        return user
