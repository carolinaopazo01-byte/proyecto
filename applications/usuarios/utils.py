# applications/usuarios/utils.py
from functools import wraps
from urllib.parse import urlencode

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from .models import Usuario

def role_required(*roles):
    """
    Usa: @role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, ...)
    - Si NO está logueado: redirige a login con ?next=<ruta_actual>.
    - Si SÍ está logueado pero no tiene el rol: 403 (evita loop al login).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                login_url = reverse("usuarios:login_rut")
                qs = urlencode({"next": request.get_full_path()})
                return redirect(f"{login_url}?{qs}")

            # Asegura que sea tu modelo y tenga atributo tipo_usuario
            if not hasattr(user, "tipo_usuario"):
                return HttpResponseForbidden("Perfil no válido.")

            if roles and user.tipo_usuario not in roles:
                return HttpResponseForbidden("No tienes permiso para acceder a esta función.")

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def any_role(*roles):
    """Helper para Python/plantillas: any_role(user, roles...) -> bool"""
    def check(user):
        return getattr(user, "is_authenticated", False) and getattr(user, "tipo_usuario", None) in roles
    return check


# --------- Utilidades RUT ---------
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
