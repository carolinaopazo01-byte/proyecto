from django import forms
from django.contrib.auth import get_user_model
from .utils import normalizar_rut, formatear_rut  # 👈 importante

Usuario = get_user_model()

class UsuarioCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repetir contraseña", widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = [
            "rut", "username", "first_name", "last_name", "email",
            "telefono", "tipo_usuario", "is_staff", "is_superuser",
        ]
        widgets = {
            "tipo_usuario": forms.Select(),
        }
        labels = {
            "rut": "RUT",
            "username": "Usuario (alias)",
            "first_name": "Nombre",
            "last_name": "Apellido",
            "telefono": "Teléfono",
            "tipo_usuario": "Rol",
            "is_staff": "Puede entrar al admin de Django",
            "is_superuser": "Superusuario total",
        }

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data.get("rut") or "")
        if not rut or "-" not in rut:
            raise forms.ValidationError("RUT inválido.")
        # Validar duplicado ignorando formato
        qs = Usuario.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.filter(rut__iexact=rut).exists():
            raise forms.ValidationError("Ya existe un usuario con ese RUT.")
        return rut

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        # 👇 Guardamos el RUT con puntos y guion
        user.rut = formatear_rut(self.cleaned_data["rut"])
        user.set_password(self.cleaned_data["password1"])
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
