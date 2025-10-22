# applications/core/migrations/0003_add_sede_comuna_fix.py
from django.db import migrations

def add_comuna_if_missing(apps, schema_editor):
    """
    En SQLite agregamos la columna 'comuna' a core_sede solo si no existe,
    y rellenamos un valor por defecto para filas antiguas.
    """
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(core_sede)")
    cols = [row[1] for row in cursor.fetchall()]
    if "comuna" not in cols:
        cursor.execute("ALTER TABLE core_sede ADD COLUMN comuna varchar(80)")
        cursor.execute("UPDATE core_sede SET comuna='Coquimbo' WHERE comuna IS NULL")

def noop(apps, schema_editor):
    pass  # no se remueve la columna en reverse (DROP COLUMN en SQLite es complejo)

class Migration(migrations.Migration):

    # ⬇️ Si tu última migración de 'core' es distinta, cámbiala aquí.
    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(add_comuna_if_missing, noop),
    ]
