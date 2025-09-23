from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AsistenciaAtleta
from applications.core.models import Comunicado

@receiver(post_save, sender=AsistenciaAtleta)
def update_faltas(sender, instance, **kwargs):
    atleta = instance.atleta
    if instance.presente:
        if atleta.faltas_consecutivas != 0:
            atleta.faltas_consecutivas = 0
            atleta.save(update_fields=['faltas_consecutivas'])
    else:
        atleta.faltas_consecutivas += 1
        atleta.save(update_fields=['faltas_consecutivas'])
        if atleta.faltas_consecutivas >= 3:
            Comunicado.objects.create(
                titulo=f"Alerta inasistencias: {atleta}",
                contenido=f"{atleta} acumula {atleta.faltas_consecutivas} faltas consecutivas."
            )