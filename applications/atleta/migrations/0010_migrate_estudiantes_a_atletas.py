from django.db import migrations

def run_forward(apps, schema_editor):
    Estudiante = apps.get_model("core", "Estudiante")
    Atleta     = apps.get_model("atleta", "Atleta")
    Inscripcion= apps.get_model("atleta", "Inscripcion")
    Usuario    = apps.get_model("usuarios", "Usuario")

    created_atletas = 0
    created_insc    = 0

    for e in Estudiante.objects.all():
        u = None
        if hasattr(Usuario, "rut") and e.rut:
            u = Usuario.objects.filter(rut=e.rut).first()

        atleta, a_created = Atleta.objects.get_or_create(
            rut=e.rut or f"E-{e.pk}",
            defaults={
                "usuario": u,
                "fecha_nacimiento": getattr(e, "fecha_nacimiento", None),
                "direccion": getattr(e, "direccion", ""),
                "comuna": getattr(e, "comuna", ""),
            }
        )
        if a_created:
            created_atletas += 1

        if getattr(e, "curso_id", None):
            _, icreated = Inscripcion.objects.get_or_create(
                atleta=atleta,
                curso=e.curso,
                defaults={"estado": "ACTIVA"},
            )
            if icreated:
                created_insc += 1

    print(f"[MIGRACIÓN] Atletas creados: {created_atletas}, Inscripciones creadas: {created_insc}")

def run_backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("atleta",  "0009_alter_atleta_usuario"),   # último de atleta
        ("core",    "0010_estudiante_apoderado_rut"),  # último de core
        ("usuarios","0003_usuario_equipo_rol"),     # último de usuarios
    ]

    operations = [
        migrations.RunPython(run_forward, run_backward),
    ]
