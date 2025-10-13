from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from .models import Usuario

def role_required(*roles):
    """
    Usa: @role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, ...)
    - Si no está logueado: lo manda al login.
    - Si está logueado pero no tiene el rol: 403.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse("usuarios:login_rut"))
            # Para asegurar que es tu modelo:
            user = request.user
            if not hasattr(user, "tipo_usuario"):
                return HttpResponseForbidden("Perfil no válido.")
            if user.tipo_usuario in roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("No tienes permiso para acceder a esta función.")
        return _wrapped
    return decorator


def any_role(*roles):
    """Helper para plantillas: any_role(request.user, roles...) -> bool"""
    def check(user):
        return getattr(user, "is_authenticated", False) and getattr(user, "tipo_usuario", None) in roles
    return check
