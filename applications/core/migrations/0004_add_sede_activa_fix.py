# applications/core/migrations/0004_add_sede_activa_fix.py
from django.db import migrations, connection


def add_activa_if_missing(apps, schema_editor):
    """
    En SQLite agrega la columna 'activa' a core_sede si no existe.
    En PostgreSQL (Render) se omite.
    """
    vendor = connection.vendor

    if vendor == "sqlite":
        cursor = schema_editor.connection.cursor()
        cursor.execute("PRAGMA table_info(core_sede)")
        cols = [row[1] for row in cursor.fetchall()]
        if "activa" not in cols:
            cursor.execute("ALTER TABLE core_sede ADD COLUMN activa INTEGER DEFAULT 1")
            cursor.execute("UPDATE core_sede SET activa=1 WHERE activa IS NULL")
            print("✅ Columna 'activa' agregada en SQLite.")
        else:
            print("ℹ️ Columna 'activa' ya existe, sin cambios.")

    elif vendor == "postgresql":
        print("⏩ Migración omitida para PostgreSQL (Render).")

    else:
        print(f"⚠️ Motor de base de datos no reconocido: {vendor}")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_add_sede_comuna_fix"),
    ]

    operations = [
        migrations.RunPython(add_activa_if_missing, noop),
    ]
