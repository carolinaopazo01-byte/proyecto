# applications/core/services.py
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from applications.core.models import PostulacionEstudiante
from applications.usuarios.models import Usuario

def _pick_attr(obj, *names):
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v:
                return v
    return None

def crear_postulacion_desde_temporal(temporal, usuario_creador):
    """
    Crea o reutiliza una PostulacionEstudiante desde un registro temporal (profesor).
    - Reabre con estado NEW si existe y NO está ACE.
    - Si está ACE, solo actualiza datos y agrega comentario.
    - REQUIERE RUT (el modelo de postulación lo tiene unique=True).
    """
    rut = (getattr(temporal, "rut", "") or "").strip()
    if not rut:
        raise ValueError("No se puede crear la postulación: falta RUT.")

    # Campos básicos (best effort)
    nombres = _pick_attr(temporal, "nombres")
    apellidos = _pick_attr(temporal, "apellidos")
    email = _pick_attr(temporal, "email")
    telefono = _pick_attr(temporal, "telefono")
    comuna = _pick_attr(temporal, "comuna")
    fecha_nacimiento = _pick_attr(temporal, "fecha_nacimiento")

    # Deporte / sede desde el temporal o su curso
    curso = _pick_attr(temporal, "curso")
    deporte_interes = _pick_attr(temporal, "deporte_interes", "deporte")
    sede_interes = _pick_attr(temporal, "sede_interes", "sede")
    if curso:
        if not deporte_interes and hasattr(curso, "deporte"):
            deporte_interes = curso.deporte
        if not sede_interes and hasattr(curso, "sede"):
            sede_interes = curso.sede

    # Período (si viene)
    periodo = _pick_attr(temporal, "periodo")

    # Mensaje base y motivación (si existe en el temporal)
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
    nota = f"[{timestamp}] {usuario_creador.get_username()}: creada desde inscripción temporal."
    motivacion = (getattr(temporal, "motivacion_beca", "") or "").strip()
    if motivacion:
        nota = f"{nota}\nMotivación: {motivacion}"

    # Buscar por RUT
    try:
        sol = PostulacionEstudiante.objects.get(rut=rut)
        existe = True
    except PostulacionEstudiante.DoesNotExist:
        sol = None
        existe = False

    # Helper para aplicar cambios y trackear update_fields
    def _apply(obj, data: dict, add_estado: str | None = None, add_comentario: str | None = None):
        update_fields = []
        for k, v in data.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
                update_fields.append(k)
        if add_estado:
            obj.estado = add_estado
            update_fields.append("estado")
        if add_comentario:
            obj.comentarios = (obj.comentarios or "").strip()
            obj.comentarios = f"{obj.comentarios}\n{add_comentario}".strip()
            if "comentarios" not in update_fields:
                update_fields.append("comentarios")
        if hasattr(obj, "modificado"):
            obj.modificado = timezone.now()
            update_fields.append("modificado")
        obj.save(update_fields=list(dict.fromkeys(update_fields)))  # sin duplicados

    if existe:
        # Si ya está ACEPTADA, NO cambiamos el estado; solo actualizamos datos útiles y comentario
        if sol.estado == PostulacionEstudiante.Estado.ACEPTADA:
            _apply(sol, {
                "nombres": nombres, "apellidos": apellidos, "email": email,
                "telefono": telefono, "comuna": comuna, "fecha_nacimiento": fecha_nacimiento,
                "deporte_interes": deporte_interes, "sede_interes": sede_interes,
                "periodo": periodo, "origen": "profesor",
            }, add_estado=None, add_comentario=nota)
        else:
            # Reabrir/poner como NEW para que el admin/coord la evalúe
            _apply(sol, {
                "nombres": nombres, "apellidos": apellidos, "email": email,
                "telefono": telefono, "comuna": comuna, "fecha_nacimiento": fecha_nacimiento,
                "deporte_interes": deporte_interes, "sede_interes": sede_interes,
                "periodo": periodo, "origen": "profesor",
            }, add_estado=PostulacionEstudiante.Estado.NUEVA, add_comentario=nota)
    else:
        # Crear nueva postulación en estado NEW
        sol = PostulacionEstudiante.objects.create(
            periodo=periodo,
            rut=rut,
            nombres=nombres or "",
            apellidos=apellidos or "",
            fecha_nacimiento=fecha_nacimiento,
            email=email,
            telefono=telefono or "",
            comuna=comuna or "",
            deporte_interes=deporte_interes,
            sede_interes=sede_interes,
            estado=PostulacionEstudiante.Estado.NUEVA,
            comentarios=nota,
            origen="profesor",
        )

    # Notificar ADMIN/COORD por email (si hay destinatarios)
    destinatarios = list(
        Usuario.objects.filter(
            tipo_usuario__in=[Usuario.Tipo.ADMIN, Usuario.Tipo.COORD],
            is_active=True,
            email__isnull=False,
        ).values_list("email", flat=True)
    )
    destinatarios = [e for e in destinatarios if e]
    if destinatarios:
        deporte_txt = str(sol.deporte_interes) if sol.deporte_interes else "—"
        sede_txt = str(sol.sede_interes) if sol.sede_interes else "—"
        try:
            creado_txt = timezone.localtime(sol.creado).strftime("%d/%m/%Y %H:%M")
        except Exception:
            creado_txt = sol.creado.strftime("%d/%m/%Y %H:%M")

        cuerpo = (
            "Nueva solicitud de inscripción temporal (creada por profesor)\n\n"
            f"Nombre: {sol.nombres} {sol.apellidos}\n"
            f"RUT: {sol.rut}\n"
            f"Deporte de interés: {deporte_txt}\n"
            f"Sede de interés: {sede_txt}\n"
            f"Fecha: {creado_txt}\n\n"
            "Revísala en el panel de Postulaciones."
        )
        send_mail(
            subject="Nueva solicitud de inscripción temporal",
            message=cuerpo,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=destinatarios,
            fail_silently=True,
        )

    return sol

def crear_estudiante_desde_postulacion(postulacion):
    """
    Crea o actualiza un Estudiante a partir de una PostulacionEstudiante aceptada.
    - Idempotente por RUT (si existe, actualiza; si no, crea).
    - Copia solo campos existentes en el modelo Estudiante.
    - Marca 'activo=True' si el modelo lo tiene.
    """
    from django.apps import apps

    Estudiante = apps.get_model("core", "Estudiante")

    rut = (getattr(postulacion, "rut", "") or "").strip()
    if not rut:
        raise ValueError("La postulación no tiene RUT; no es posible crear el Estudiante.")

    # Obtiene o crea
    est = Estudiante.objects.filter(rut=rut).first()
    created = False
    if not est:
        est = Estudiante(rut=rut)
        created = True

    # Mapeo de campos disponibles en la postulación
    data = {
        "nombres": getattr(postulacion, "nombres", None),
        "apellidos": getattr(postulacion, "apellidos", None),
        "fecha_nacimiento": getattr(postulacion, "fecha_nacimiento", None),
        "email": getattr(postulacion, "email", None),
        "telefono": getattr(postulacion, "telefono", None),
        "comuna": getattr(postulacion, "comuna", None),
        # Si tu modelo Estudiante tiene estos campos, se asignarán:
        "direccion": getattr(postulacion, "direccion", None),           # usualmente no existe en la postulación
        "n_emergencia": getattr(postulacion, "n_emergencia", None),     # idem
        "prevision": getattr(postulacion, "prevision", None),           # idem
    }

    # Asignación defensiva (solo si el campo existe en Estudiante y hay valor)
    for field, value in data.items():
        if value not in [None, ""] and hasattr(est, field):
            setattr(est, field, value)

    # Activo = True si el modelo lo tiene
    if hasattr(est, "activo") and est.activo is not True:
        est.activo = True

    # (Opcional) Si Estudiante tiene FK a Curso y puedes inferirlo aquí, asígnalo:
    # if hasattr(est, "curso") and getattr(est, "curso_id", None) is None:
    #     # La Postulación no tiene 'curso'; si quieres persistirlo, guarda ese dato en la postulación al crearla.
    #     pass

    est.save()
    return est, created
