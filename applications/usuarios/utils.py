from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from .models import Usuario

def rut_equivalente(rut):
    """Convierte cualquier formato de RUT a uno comparable, solo números y DV."""
    if not rut:
        return ""
    return rut.replace(".", "").replace("-", "").strip().upper()

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

# applications/usuarios/utils.py

def normalizar_rut(rut: str) -> str:
    """Devuelve 'XXXXXXXX-DV' (sin puntos, con guion). No valida DV."""
    if not rut:
        return ""
    s = "".join(c for c in rut if c.isdigit() or c.upper() == "K")
    if len(s) < 2:
        return s
    base, dv = s[:-1], s[-1].upper()
    return f"{base}-{dv}"

def formatear_rut(rut: str) -> str:
    """Formatea con puntos + guion. No valida DV."""
    nr = normalizar_rut(rut)
    if "-" not in nr:
        return nr
    base, dv = nr.split("-")
    partes = []
    while len(base) > 3:
        partes.insert(0, base[-3:])
        base = base[:-3]
    if base:
        partes.insert(0, base)
    return ".".join(partes) + "-" + dv
