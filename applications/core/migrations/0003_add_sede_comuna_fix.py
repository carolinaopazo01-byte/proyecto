# applications/core/migrations/0003_add_sede_comuna_fix.py
from django.db import migrations, connection


def add_comuna_if_missing(apps, schema_editor):
    """
    En SQLite agregamos la columna 'comuna' a core_sede solo si no existe.
    En PostgreSQL (Render) se omite, ya que no aplica PRAGMA.
    """
    vendor = connection.vendor

    if vendor == "sqlite":
        cursor = schema_editor.connection.cursor()
        cursor.execute("PRAGMA table_info(core_sede)")
        cols = [row[1] for row in cursor.fetchall()]
        if "comuna" not in cols:
            cursor.execute("ALTER TABLE core_sede ADD COLUMN comuna varchar(80)")
            cursor.execute("UPDATE core_sede SET comuna='Coquimbo' WHERE comuna IS NULL")
            print("✅ Columna 'comuna' agregada en SQLite.")
        else:
            print("ℹ️ Columna 'comuna' ya existe, sin cambios.")

    elif vendor == "postgresql":
        # PostgreSQL no usa PRAGMA, así que lo ignoramos
        print("⏩ Migración omitida para PostgreSQL (Render).")

    else:
        print(f"⚠️ Motor de base de datos no reconocido: {vendor}")


def noop(apps, schema_editor):
    pass  # No revertimos (DROP COLUMN en SQLite es complejo)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(add_comuna_if_missing, noop),
    ]
