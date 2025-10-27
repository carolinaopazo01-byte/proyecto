from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AsistenciaAtleta

from applications.core.models import Comunicado, Estudiante
from applications.atleta.models import Atleta, Inscripcion
from applications.usuarios.utils import normalizar_rut, formatear_rut

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

@receiver(post_save, sender=Estudiante)
def sync_inscripcion_desde_estudiante(sender, instance: Estudiante, **kwargs):
    """
    Cada vez que se guarda un Estudiante:
    - Busca el Atleta con el mismo RUT (con y sin puntos).
    - Si el Estudiante tiene curso, crea/actualiza la Inscripcion.
    - Si Estudiante está inactivo, marca la inscripción INACTIVA.
    """
    if not instance.rut:
        return

    rut_norm = normalizar_rut(instance.rut)
    atleta = Atleta.objects.filter(rut__in=[rut_norm, formatear_rut(rut_norm)]).first()
    if not atleta:
        return

    curso = getattr(instance, "curso", None)
    if not curso:
        return

    ins, created = Inscripcion.objects.get_or_create(
        atleta=atleta,
        curso=curso,
        defaults={"estado": "ACTIVA"},
    )
    # Si la ficha de estudiante tiene flag "activo", úsalo para estado; si no, siempre ACTIVA
    activo = getattr(instance, "activo", True)
    nuevo_estado = "ACTIVA" if activo else "INACTIVA"
    if ins.estado != nuevo_estado:
        ins.estado = nuevo_estado
        ins.save(update_fields=["estado"])