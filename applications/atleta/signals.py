from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AsistenciaAtleta
from applications.core.models import Comunicado

@receiver(post_save, sender=AsistenciaAtleta)
def update_faltas(sender, instance, **kwargs):
    at = instance.atleta
    if not at:
        return

    if instance.presente:
        # presente => reinicia
        if at.faltas_consecutivas != 0:
            at.faltas_consecutivas = 0
            at.save(update_fields=["faltas_consecutivas"])
        return

    # ausente
    if instance.justificada:
        # justificada => NO suma
        return

    at.faltas_consecutivas += 1
    at.save(update_fields=["faltas_consecutivas"])
    if at.faltas_consecutivas >= 3:
        Comunicado.objects.create(
            titulo=f"Alerta inasistencias: {at}",
            cuerpo=f"{at} acumula {at.faltas_consecutivas} faltas consecutivas."
        )