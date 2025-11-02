#applications/usuarios/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .utils import normalizar_rut, formatear_rut
from datetime import date
from .models import Usuario

Usuario = get_user_model()

def _rut_calc_dv(numero: str) -> str:
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

def normalizar_rut(ch: str) -> str:
    ch = (ch or "").strip().upper().replace(".", "").replace(" ", "")
    if "-" not in ch and len(ch) >= 2:
        ch = ch[:-1] + "-" + ch[-1]
    return ch

def formatear_rut(ch: str) -> str:
    ch = normalizar_rut(ch)
    base, dv = ch.split("-")
    partes = []
    while len(base) > 3:
        partes.insert(0, base[-3:])
        base = base[:-3]
    if base:
        partes.insert(0, base)
    return ".".join(partes) + "-" + dv


class UsuarioCreateForm(forms.ModelForm):
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=True,
        label="Fecha de nacimiento"
    )
    is_active = forms.BooleanField(initial=True, required=False, label="Activo")

    class Meta:
        model = Usuario
        fields = [
            "rut", "first_name", "last_name", "email", "telefono",
            "fecha_nacimiento", "tipo_usuario", "equipo_rol",  # 👈 AÑADIDO
            "is_active",
        ]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "telefono": "Teléfono (ej: 9 99999999)",
            "tipo_usuario": "Rol",
            "equipo_rol": "Sub-rol (Equipo Multidisciplinario)",
        }

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("tipo_usuario")
        subrol = cleaned.get("equipo_rol")
        if rol == Usuario.Tipo.PMUL and not subrol:
            self.add_error("equipo_rol", "Selecciona el sub-rol del Equipo Multidisciplinario.")
        if rol != Usuario.Tipo.PMUL:
            cleaned["equipo_rol"] = None
        return cleaned

    def clean_rut(self):
        rut = self.cleaned_data.get("rut", "")
        rut = normalizar_rut(rut)
        try:
            base, dv = rut.split("-")
        except ValueError:
            raise ValidationError("RUT inválido.")
        if not base.isdigit() or len(base) < 6:
            raise ValidationError("RUT inválido.")
        if _rut_calc_dv(base) != dv.upper():
            raise ValidationError("Dígito verificador incorrecto.")
        if Usuario.objects.filter(rut__iexact=formatear_rut(base + dv)).exists():
            raise ValidationError("Ya existe un usuario con ese RUT.")
        return formatear_rut(base + dv)

    def save(self, commit=True):
        data = self.cleaned_data
        username = normalizar_rut(data["rut"]).replace(".", "").replace("-", "")
        user = Usuario(
            username=username,
            rut=data["rut"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            telefono=data.get("telefono") or "",
            tipo_usuario=data["tipo_usuario"],
            equipo_rol=data.get("equipo_rol"),  # 👈 guarda sub-rol
            is_active=data.get("is_active", True),
        )
        if user.tipo_usuario == Usuario.Tipo.ADMIN:
            user.is_staff = True
            user.is_superuser = True
        elif user.tipo_usuario == Usuario.Tipo.COORD:
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        fn = data["fecha_nacimiento"]
        pwd = f"{fn.day:02d}{fn.month:02d}{fn.year:04d}"
        user.set_password(pwd)

        if commit:
            user.save()
        return user


class UsuarioUpdateForm(forms.ModelForm):
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        label="Fecha de nacimiento"
    )

    class Meta:
        model = Usuario
        fields = [
            "rut", "first_name", "last_name", "email", "telefono",
            "tipo_usuario", "equipo_rol",  # 👈 AÑADIDO
            "is_active", "fecha_nacimiento",
        ]
        widgets = {"rut": forms.TextInput(attrs={"readonly": "readonly"})}
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "tipo_usuario": "Rol",
            "equipo_rol": "Sub-rol (Equipo Multidisciplinario)",
            "is_active": "Activo",
        }

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("tipo_usuario")
        subrol = cleaned.get("equipo_rol")
        if rol == Usuario.Tipo.PMUL and not subrol:
            self.add_error("equipo_rol", "Selecciona el sub-rol del Equipo Multidisciplinario.")
        if rol != Usuario.Tipo.PMUL:
            cleaned["equipo_rol"] = None
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
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