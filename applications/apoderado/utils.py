# applications/apoderado/utils.py
from datetime import datetime, timedelta, time
from django.apps import apps
from django.db.models import Q, Count
from django.utils import timezone

def get_model(label):
    """
    Carga un modelo como 'app.Model' y retorna None si no existe,
    en lugar de lanzar LookupError.
    """
    try:
        app_label, model_name = label.split(".")
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

def hijos_de_apoderado(user):
    """
    Devuelve queryset/lista de atletas (estudiantes) asociados al apoderado.
    Intenta varios esquemas: FK a Usuario, rut, email, etc.
    """
    Estudiante = get_model("core.Estudiante") or get_model("atleta.Estudiante")
    if not Estudiante:
        return Estudiante  # None

    # 1) si existe FK a usuario apoderado
    if "apoderado" in [f.name for f in Estudiante._meta.fields]:
        return Estudiante.objects.filter(apoderado=user)

    # 2) por RUT del apoderado guardado como texto
    rut = getattr(user, "rut", "") or getattr(user, "username", "")
    qs = Estudiante.objects.all()
    if "apoderado_rut" in [f.name for f in Estudiante._meta.fields]:
        return qs.filter(apoderado_rut__iexact=rut)

    # 3) por email de contacto
    mail = (user.email or "").lower()
    if "apoderado_email" in [f.name for f in Estudiante._meta.fields] and mail:
        return qs.filter(apoderado_email__iexact=mail)

    # 4) sin vínculo explícito: devolvemos “todos activos” (último recurso)
    campos = [f.name for f in Estudiante._meta.fields]
    if "activo" in campos:
        return qs.filter(activo=True)
    return qs

def porcentaje_asistencia_semana(estudiante):
    """
    Calcula % de asistencia de la semana del atleta si hay modelo de asistencia.
    Busca nombres comunes: core.AsistenciaAtleta, core.AsistenciaAlumno, atleta.Asistencia.
    """
    hoy = timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    Asis = (get_model("core.AsistenciaAtleta") or
            get_model("core.AsistenciaAlumno") or
            get_model("atleta.Asistencia"))
    if not Asis:
        return None

    qs = Asis.objects.filter(fecha__range=(lunes, domingo))
    # detectar campo FK hacia estudiante
    fk_name = None
    for f in Asis._meta.fields:
        if f.is_relation and getattr(f.related_model, "_meta", None) and f.related_model._meta.model_name.lower() == estudiante._meta.model_name.lower():
            fk_name = f.name
            break
    if not fk_name:
        return None

    tot = qs.filter(**{fk_name: estudiante}).count()
    if tot == 0:
        return 0
    presentes = qs.filter(**{fk_name: estudiante, "presente": True}).count() if "presente" in [f.name for f in Asis._meta.fields] else 0
    return round((presentes / max(tot, 1)) * 100)

def proxima_clase_de(estudiante):
    """
    Busca próxima clase según CursoHorario si existe relación estudiante->curso.
    """
    Curso = get_model("core.Curso")
    CursoHorario = get_model("core.CursoHorario")
    if not (Curso and CursoHorario):
        return None

    # ¿cómo está vinculado el estudiante con un curso? probamos varias:
    curso = None
    # a) FK directa
    if "curso" in [f.name for f in estudiante._meta.fields]:
        curso = getattr(estudiante, "curso", None)

    # b) por inscripción intermedia
    if not curso:
        Ins = (get_model("core.Inscripcion") or get_model("atleta.Inscripcion") or get_model("atleta.InscripcionCurso"))
        if Ins:
            # detectar campo FK hacia estudiante
            fk_est = None
            for f in Ins._meta.fields:
                if f.is_relation and f.related_model == estudiante._meta.model:
                    fk_est = f.name
                    break
            if fk_est and "curso" in [f.name for f in Ins._meta.fields]:
                ins = Ins.objects.filter(**{fk_est: estudiante}).order_by("-id").first()
                if ins:
                    curso = getattr(ins, "curso", None)

    if not curso:
        return None

    ahora = timezone.localtime()
    # Buscar próximos horarios de la semana (día y hora)
    horarios = CursoHorario.objects.filter(curso=curso).order_by("dia", "hora_inicio")
    if not horarios.exists():
        return None

    # calcular siguiente ocurrencia
    for add_d in range(0, 14):
        d = ahora.date() + timedelta(days=add_d)
        dow = d.weekday()  # 0 lunes .. 6 domingo
        for h in horarios.filter(dia=dow):
            dt_inicio = timezone.make_aware(datetime.combine(d, h.hora_inicio))
            if dt_inicio >= ahora:
                return {"fecha": d, "hora": h.hora_inicio, "curso": curso}
    return None

def proximas_citas_para(estudiante):
    """Cuenta próximas citas PMUL del atleta."""
    Cita = get_model("pmul.Cita")
    if not Cita:
        return 0
    ahora = timezone.now()
    try:
        return Cita.objects.filter(paciente=estudiante, inicio__gte=ahora, estado__in=["PEND", "REPROG"]).count()
    except Exception:
        return 0
