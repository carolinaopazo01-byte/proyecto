# applications/atleta/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import AsistenciaAtleta
from applications.core.models import Comunicado


def _find_author(curso):
    """
    Devuelve un autor válido:
    1) el profesor del curso (si existe),
    2) un superusuario,
    3) cualquier usuario existente.
    """
    if curso is not None:
        prof = getattr(curso, "profesor", None)
        if prof:
            return prof

    User = get_user_model()
    su = User.objects.filter(is_superuser=True).first()
    if su:
        return su

    return User.objects.order_by("id").first()


@receiver(post_save, sender=AsistenciaAtleta)
def update_faltas(sender, instance: AsistenciaAtleta, **kwargs):
    """
    Cuenta faltas consecutivas del atleta. Si llega a 3, emite un Comunicado.
    SOLO usa campos que existen en tu modelo (titulo, cuerpo, autor).
    """
    atleta = getattr(instance, "atleta", None)
    if not atleta:
        return

    # Resetear / incrementar contador
    if instance.presente or instance.justificado:
        if getattr(atleta, "faltas_consecutivas", 0) != 0:
            atleta.faltas_consecutivas = 0
            atleta.save(update_fields=["faltas_consecutivas"])
        return

    atleta.faltas_consecutivas = (getattr(atleta, "faltas_consecutivas", 0) or 0) + 1
    atleta.save(update_fields=["faltas_consecutivas"])

    # Umbral
    if atleta.faltas_consecutivas < 3:
        return

    curso = getattr(getattr(instance, "clase", None), "curso", None)
    autor = _find_author(curso)
    if not autor:
        # No hay nadie a quien asignar como autor -> salimos para evitar IntegrityError
        return

    titulo = f"Alerta de inasistencias: {atleta}"
    cuerpo = f"{atleta} acumula {atleta.faltas_consecutivas} faltas consecutivas."

    Comunicado.objects.create(titulo=titulo, cuerpo=cuerpo, autor=autor)
