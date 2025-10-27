from django.db import migrations

def add_activa_if_missing(apps, schema_editor):
    """
    En SQLite añadimos la columna 'activa' a core_sede sólo si no existe.
    La dejamos con 1 (True) para filas antiguas.
    """
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(core_sede)")
    cols = [row[1] for row in cursor.fetchall()]
    if "activa" not in cols:
        # SQLite usa 0/1 para boolean
        cursor.execute("ALTER TABLE core_sede ADD COLUMN activa boolean")
        cursor.execute("UPDATE core_sede SET activa = 1 WHERE activa IS NULL")

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    # ⚠️ Ajusta la dependencia al último archivo de 'core' que tengas
    dependencies = [
        ("core", "0003_add_sede_comuna_fix"),
    ]

    operations = [
        migrations.RunPython(add_activa_if_missing, noop),
    ]
