# applications/usuarios/auth_backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db.models import Q

from .utils import normalizar_rut, formatear_rut

User = get_user_model()

class RutBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        rut_input = (username or "").strip()
        rut_norm = normalizar_rut(rut_input)      # 12345678-9
        rut_fmt  = formatear_rut(rut_norm)        # 12.345.678-9

        if not rut_norm or not password:
            return None

        try:
            # Acepta lo que esté guardado: normalizado o formateado
            user = User.objects.get(Q(rut=rut_norm) | Q(rut=rut_fmt))
        except User.DoesNotExist:
            return None

        return user if check_password(password, user.password) else None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
