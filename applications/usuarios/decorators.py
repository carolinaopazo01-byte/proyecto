# applications/usuarios/decorators.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

def role_required(*roles):
    """
    Uso: @role_required("ATLE")  ó  @role_required("ADMIN","COORD")
    Requiere que el usuario esté autenticado y que su atributo
    user.tipo_usuario esté en el conjunto de roles permitidos.
    """
    roles = {r.upper() for r in roles}

    def decorator(viewfunc):
        @wraps(viewfunc)
        @login_required
        def _wrapped(request, *args, **kwargs):
            tipo = (getattr(request.user, "tipo_usuario", "") or "").upper()
            if roles and tipo not in roles:
                return HttpResponseForbidden("No tienes permiso para acceder aquí.")
            return viewfunc(request, *args, **kwargs)
        return _wrapped
    return decorator
