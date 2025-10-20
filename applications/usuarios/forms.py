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
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=True, label="Fecha de nacimiento")
    is_active = forms.BooleanField(initial=True, required=False, label="Activo")

    class Meta:
        model = Usuario
        fields = ["rut", "first_name", "last_name", "email", "telefono", "fecha_nacimiento", "tipo_usuario",
                  "is_active"]
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "telefono": "Teléfono (ej: 9 99999999)",
            "tipo_usuario": "Rol",
        }

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
        # unicidad sin formato
        if Usuario.objects.filter(rut__iexact=formatear_rut(base + dv)).exists():
            raise ValidationError("Ya existe un usuario con ese RUT.")
        return formatear_rut(base + dv)

    def save(self, commit=True):
        data = self.cleaned_data
        # username desde el RUT sin puntos ni guion
        username = normalizar_rut(data["rut"]).replace(".", "").replace("-", "")
        user = Usuario(
            username=username,
            rut=data["rut"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            telefono=data.get("telefono") or "",
            tipo_usuario=data["tipo_usuario"],
            is_active=data.get("is_active", True),
        )
        # permisos por rol (no editables aquí)
        if user.tipo_usuario == Usuario.Tipo.ADMIN:
            user.is_staff = True
            user.is_superuser = True
        elif user.tipo_usuario == Usuario.Tipo.COORD:
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False

        # contraseña DDMMAAAA con fecha de nacimiento
        fn = data["fecha_nacimiento"]
        pwd = f"{fn.day:02d}{fn.month:02d}{fn.year:04d}"
        user.set_password(pwd)

        if commit:
            user.save()
        return user

class UsuarioUpdateForm(forms.ModelForm):
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False, label="Fecha de nacimiento")

    class Meta:
        model = Usuario
        fields = ["rut", "first_name", "last_name", "email", "telefono", "tipo_usuario", "is_active", "fecha_nacimiento"]
        widgets = {
            "rut": forms.TextInput(attrs={"readonly": "readonly"}),
        }
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "tipo_usuario": "Rol",
            "is_active": "Activo",
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        # ajustar staff/superuser según rol
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

class UsuarioEditForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "rut", "username", "first_name", "last_name", "email",
            "telefono", "tipo_usuario", "is_staff", "is_superuser",
        ]

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data.get("rut") or "")
        if not rut or "-" not in rut:
            raise forms.ValidationError("RUT inválido.")
        qs = Usuario.objects.exclude(pk=self.instance.pk)
        if qs.filter(rut__iexact=rut).exists():
            raise forms.ValidationError("Ya existe un usuario con ese RUT.")
        return rut

    def save(self, commit=True):
        user = super().save(commit=False)
        # 👇 También aquí guardamos el formato con puntos
        user.rut = formatear_rut(self.cleaned_data["rut"])
        if commit:
            user.save()
        return user
