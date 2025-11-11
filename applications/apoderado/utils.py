# applications/apoderado/utils.py
from datetime import datetime, timedelta
from django.apps import apps
from django.utils import timezone


def _rut_normaliza(rut: str) -> str:
    if not rut:
        return ""
    r = rut.strip().replace(".", "").replace(" ", "").replace("–","-").replace("—","-").upper()
    if "-" not in r and len(r) >= 2:
        r = r[:-1] + "-" + r[-1]
    if "-" in r:
        base, dv = r.split("-", 1)
        r = f"{base}-{dv.upper()}"
    return r

def get_model(label):
    try:
        app_label, model_name = label.split(".")
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

def hijos_de_apoderado(user):
    Estudiante = get_model("core.Estudiante") or get_model("atleta.Estudiante")
    if not Estudiante:
        return Estudiante

    qs = Estudiante.objects.all()
    campos = [f.name for f in Estudiante._meta.fields]

    # 1) FK directa
    if "apoderado" in campos:
        return qs.filter(apoderado=user)

    # 2) por RUT
    if "apoderado_rut" in campos:
        rut_user = _rut_normaliza(getattr(user, "rut", "") or getattr(user, "username", ""))
        if rut_user:
            return qs.filter(apoderado_rut__iexact=rut_user)

    # 3) por email si lo almacenas
    if "apoderado_email" in campos and user.email:
        return qs.filter(apoderado_email__iexact=(user.email or "").lower())

    # 4) último recurso (evita traer todos): mejor devuelve vacío
    return qs.none()


def porcentaje_asistencia_semana(estudiante):
    """
    Calcula % de asistencia de la semana del atleta si hay modelo de asistencia.
    Busca nombres comunes: core.AsistenciaAtleta, core.AsistenciaAlumno, atleta.Asistencia.
    Usa asistencia__fecha (fecha está en la cabecera AsistenciaClase).
    """
    if not estudiante:
        return None

    hoy = timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    Asis = (
        get_model("core.AsistenciaAtleta")
        or get_model("core.AsistenciaAlumno")
        or get_model("atleta.Asistencia")
    )
    if not Asis:
        return None

    # detectar el nombre del FK hacia el estudiante (p.ej. 'estudiante' o 'atleta')
    fk_name = None
    for f in Asis._meta.fields:
        if f.is_relation and getattr(f, "related_model", None):
            if f.related_model == estudiante.__class__:
                fk_name = f.name
                break
    if not fk_name:
        return None

    base = Asis.objects.filter(asistencia__fecha__range=(lunes, domingo))
    tot = base.filter(**{fk_name: estudiante}).count()
    if tot == 0:
        return 0

    # 'presente' puede no existir en algunos esquemas
    if "presente" in [f.name for f in Asis._meta.fields]:
        presentes = base.filter(**{fk_name: estudiante, "presente": True}).count()
    else:
        presentes = 0
    return round((presentes / max(tot, 1)) * 100)


def proxima_clase_de(estudiante):

    if not estudiante:
        return None

    Curso = get_model("core.Curso")
    CursoHorario = get_model("core.CursoHorario")
    if not (Curso and CursoHorario):
        return None


    curso = None

    if "curso" in [f.name for f in estudiante._meta.fields]:
        curso = getattr(estudiante, "curso", None)


    if not curso:
        Ins = (
            get_model("core.Inscripcion")
            or get_model("atleta.Inscripcion")
            or get_model("atleta.InscripcionCurso")
        )
        if Ins:
            # detectar campo FK hacia estudiante
            fk_est = None
            for f in Ins._meta.fields:
                if f.is_relation and getattr(f, "related_model", None) == estudiante.__class__:
                    fk_est = f.name
                    break
            if fk_est and "curso" in [f.name for f in Ins._meta.fields]:
                ins = Ins.objects.filter(**{fk_est: estudiante}).order_by("-id").first()
                if ins:
                    curso = getattr(ins, "curso", None)

    if not curso:
        return None

    ahora = timezone.localtime()

    horarios = CursoHorario.objects.filter(curso=curso).order_by("dia", "hora_inicio")
    if not horarios.exists():
        return None


    for add_d in range(0, 14):
        d = ahora.date() + timedelta(days=add_d)
        dow = d.weekday()  # 0 lunes .. 6 domingo
        for h in horarios.filter(dia=dow):
            dt_inicio = timezone.make_aware(datetime.combine(d, h.hora_inicio))
            if dt_inicio >= ahora:
                return {"fecha": d, "hora": h.hora_inicio, "curso": curso}
    return None


def proximas_citas_para(estudiante):

    if not estudiante:
        return 0
    Cita = get_model("pmul.Cita")
    if not Cita:
        return 0
    ahora = timezone.now()
    try:
        return Cita.objects.filter(
            paciente=estudiante,
            inicio__gte=ahora,
            estado__in=["PEND", "REPROG"],
        ).count()
    except Exception:
        return 0

def curso_actual_de(estudiante):

    Curso = get_model("core.Curso")
    if not Curso:
        return None


    if hasattr(estudiante, "curso") and estudiante.curso_id:
        return estudiante.curso


    Ins = (get_model("core.Inscripcion") or get_model("atleta.Inscripcion") or get_model("atleta.InscripcionCurso"))
    if Ins and hasattr(Ins, "_meta"):
        fk_est = None
        for f in Ins._meta.fields:
            if f.is_relation and f.related_model == estudiante._meta.model:
                fk_est = f.name
                break
        if fk_est and "curso" in [f.name for f in Ins._meta.fields]:
            ins = Ins.objects.filter(**{fk_est: estudiante}).order_by("-id").first()
            if ins:
                return getattr(ins, "curso", None)
    return None
