# applications/usuarios/utils.py
from functools import wraps
from urllib.parse import urlencode

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse


# --------------------------------------------------------------------------------------
# Decoradores de rol
# --------------------------------------------------------------------------------------
def role_required(*roles):
    """
    Uso:
        @role_required('ADMIN', 'COORD', ...)
        @role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD, ...)

    Comportamiento:
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

            # Comprobamos atributo de rol sin importar el modelo concreto
            tipo = getattr(user, "tipo_usuario", None)
            if tipo is None:
                return HttpResponseForbidden("Perfil no válido.")

            if roles and tipo not in roles:
                return HttpResponseForbidden("No tienes permiso para acceder a esta función.")

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def any_role(*roles):
    """
    Helper para Python/plantillas:
        any_role('ADMIN','COORD')(request.user) -> bool
    """
    def check(user):
        return getattr(user, "is_authenticated", False) and getattr(user, "tipo_usuario", None) in roles
    return check


# --------------------------------------------------------------------------------------
# Utilidades RUT
# --------------------------------------------------------------------------------------
def _strip_rut_chars(s: str) -> str:
    """Quita puntos y espacios, normaliza guiones Unicode a '-' y pasa DV a mayúscula."""
    if not s:
        return ""
    s = s.strip().replace(".", "").replace(" ", "")
    # Normaliza guiones “raros”
    s = s.replace("–", "-").replace("—", "-").replace("-", "-")  # en-dash, em-dash, no-break hyphen
    return s.upper()


def normalizar_rut(rut: str) -> str:
    """
    Devuelve 'XXXXXXXX-DV' (sin puntos, con guion). No valida DV.
    Si no hay suficientes caracteres, devuelve la mejor forma posible.
    """
    if not rut:
        return ""
    s = _strip_rut_chars(rut)
    # Dejar solo dígitos + 'K'
    s = "".join(c for c in s if c.isdigit() or c == "K")
    if len(s) < 2:
        # No hay base + dv suficientes
        return s
    base, dv = s[:-1], s[-1]
    return f"{base}-{dv}"


def formatear_rut(rut: str) -> str:
    """
    Formatea un RUT ya normalizado a 'XX.XXX.XXX-DV'.
    No valida DV; usa normalizar_rut internamente.
    """
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


def rut_equivalente(rut: str) -> str:
    """
    Convierte cualquier formato de RUT a uno comparable:
    'XXXXXXXX-DV' (sin puntos). Útil para comparaciones/duplicados.
    """
    return normalizar_rut(rut)
