# applications/core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Estudiante

Usuario = get_user_model()

def _username_from_rut(rut: str) -> str:
    # normaliza: quita puntos/espacios y usa mayúsculas para K
    if not rut:
        return ""
    r = rut.replace(".", "").replace(" ", "").replace("–", "-").replace("—", "-").upper()
    if "-" not in r and len(r) >= 2:
        r = r[:-1] + "-" + r[-1]
    base, dv = r.split("-", 1)
    return f"{base}-{dv}"

@receiver(post_save, sender=Estudiante)
def sync_estudiante_usuario(sender, instance: Estudiante, created, **kwargs):
    """Crea/actualiza un Usuario tipo ATLE vinculado al Estudiante."""
    rut_norm = _username_from_rut(instance.rut or "")
    if not rut_norm:
        return

    u, _ = Usuario.objects.get_or_create(rut=rut_norm, defaults={
        "username": rut_norm,
        "first_name": (instance.nombres or "")[:150],
        "last_name": (instance.apellidos or "")[:150],
        "email": instance.email or "",
        "tipo_usuario": "ATLE",   # <- MUY IMPORTANTE
        "is_active": True,
    })

    # Mantén datos sincronizados
    changed = False
    for field, value in [
        ("username", rut_norm),
        ("first_name", (instance.nombres or "")[:150]),
        ("last_name", (instance.apellidos or "")[:150]),
        ("email", instance.email or ""),
        ("tipo_usuario", "ATLE"),
        ("is_active", True),
    ]:
        if getattr(u, field) != value:
            setattr(u, field, value)
            changed = True

    # Si el usuario recién se creó y el estudiante tiene fecha_nacimiento,
    # setea contraseña DDMMAAAA; si no, una temporal.
    if created:
        if instance.fecha_nacimiento:
            fn = instance.fecha_nacimiento
            pwd = f"{fn.day:02d}{fn.month:02d}{fn.year:04d}"
        else:
            pwd = "Temporal123!"
        u.set_password(pwd)
        changed = True

    if changed:
        u.save()
