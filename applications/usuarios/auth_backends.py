from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from .models import normalizar_rut

User = get_user_model()

class RutBackend(BaseBackend):
    """
    Autentica usando rut y password en el modelo personalizado Usuario.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        rut = normalizar_rut(username or "")
        if not rut or not password:
            return None
        try:
            user = User.objects.get(rut=rut)
        except User.DoesNotExist:
            return None
        if check_password(password, user.password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
