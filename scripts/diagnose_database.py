"""Diagnóstico de solo lectura: configuración, conexión, tablas y migraciones."""

import os
from pathlib import Path
import sys


def main():
    base_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(base_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "veterinaria.settings")

    try:
        import django
        from django.core.exceptions import ImproperlyConfigured
        from django.db import DatabaseError, connection
        from django.db.migrations.exceptions import InconsistentMigrationHistory
        from django.db.migrations.executor import MigrationExecutor
    except ImportError:
        print("Faltan dependencias. Ejecuta con .venv\\Scripts\\python.exe y "
              "usa -m pip install -r requirements.txt.")
        return 1

    try:
        django.setup()
    except ImproperlyConfigured as exc:
        # Los mensajes de validación propios no incluyen valores de las variables.
        print(f"Configuración inválida: {exc}")
        return 1
    except ImportError:
        print("No se pudo cargar una dependencia. Reinstala requirements.txt "
              "con el Python de .venv.")
        return 1

    print("Configuración válida. Comprobando MySQL sin modificar datos...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                print("MySQL devolvió una respuesta inesperada a SELECT 1.")
                return 1
            existing_tables = set(connection.introspection.table_names(cursor))
        print("Conexión y autenticación MySQL: OK.")

        from django.apps import apps

        required_tables = {
            model._meta.db_table for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        }
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            print("Tablas pendientes: " + ", ".join(missing_tables))

        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            print("Migraciones pendientes: " + ", ".join(
                f"{migration.app_label}.{migration.name}" for migration, _ in plan
            ))
        if missing_tables or plan:
            print("Revisa manage.py migrate --plan antes de aplicar cambios. "
                  "Este diagnóstico no crea tablas ni restaura backup.sql.")
            return 1
        print("Tablas esperadas e historial de migraciones: OK.")
        return 0
    except InconsistentMigrationHistory:
        print("Historial de migraciones inconsistente. Revisa showmigrations y "
              "el esquema antes de aplicar cambios; no uses --fake automáticamente.")
        return 1
    except DatabaseError as exc:
        number = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        reasons = {
            2005: "No se pudo resolver el dominio. Revisa DB_HOST y el DNS de Windows.",
            2002: "No se pudo abrir la conexión. Revisa el dominio, puerto y servicio MySQL.",
            2003: "No se pudo alcanzar MySQL. Revisa el TCP Proxy, puerto externo, red y firewall.",
            1045: "MySQL rechazó las credenciales. Revisa DB_USER y DB_PASSWORD.",
            1044: "El usuario no tiene permisos sobre la base de datos configurada.",
            1049: "La base de datos indicada en DB_NAME no existe.",
            2026: "Falló la conexión TLS. Revisa los requisitos de certificados del servicio.",
        }
        detail = reasons.get(number, "No se pudo completar la comprobación MySQL. "
                             "Revisa la versión del servidor, su estado y permisos.")
        print(f"Error MySQL ({number if number is not None else type(exc).__name__}): {detail}")
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
