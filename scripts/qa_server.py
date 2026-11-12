r"""Servidor de comprobación aislado; no usa .env ni la base de Railway.

Uso: .venv\Scripts\python.exe scripts\qa_server.py
Abre http://127.0.0.1:8765/ y usa el usuario/clave de prueba indicados aquí.
"""

import argparse
from pathlib import Path
import sys


QA_USERNAME = "qa-admin"
QA_PASSWORD = "VetCare-QA-only-2026"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or args.port == 8000:
        parser.error("Usa un puerto de prueba entre 1024 y 65535 distinto de 8000.")

    base_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(base_dir))
    qa_dir = base_dir / ".qa"
    qa_dir.mkdir(exist_ok=True)
    database_path = (qa_dir / "e2e.sqlite3").resolve()
    if database_path.parent != qa_dir.resolve():
        raise RuntimeError("La base de QA debe permanecer dentro de .qa.")

    from veterinaria import test_settings
    from django.conf import settings

    isolated = {name: value for name, value in vars(test_settings).items() if name.isupper()}
    isolated.update(
        DEBUG=True,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database_path}},
    )
    settings.configure(**isolated)

    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import connection, transaction
    from empleado.models import Empleado
    from empl_veterinario.models import Veterinario

    if connection.vendor != "sqlite" or Path(connection.settings_dict["NAME"]).resolve() != database_path:
        raise RuntimeError("El servidor de QA solo admite su SQLite local.")
    call_command("migrate", interactive=False, verbosity=0)
    with transaction.atomic():
        user, _ = get_user_model().objects.get_or_create(username=QA_USERNAME)
        user.first_name = "Auditoría"
        user.last_name = "Local"
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(QA_PASSWORD)
        user.save()
        vet_employee, _ = Empleado.objects.get_or_create(
            nombre="Veterinaria", apellido="QA", defaults={"telefono": "", "cargo": "Veterinario"}
        )
        Veterinario.objects.get_or_create(
            id_veterinario=vet_employee, defaults={"especialidad": "Medicina interna"}
        )
        Empleado.objects.get_or_create(
            nombre="Adopciones", apellido="QA",
            defaults={"telefono": "", "cargo": "Encargado de adopciones"},
        )

    print("Servidor de QA aislado: SQLite local; sin .env ni conexión a Railway.", flush=True)
    print(f"URL: http://127.0.0.1:{args.port}/", flush=True)
    print(f"Usuario exclusivo de pruebas: {QA_USERNAME}", flush=True)
    print(f"Clave exclusiva de pruebas: {QA_PASSWORD}", flush=True)
    if not args.prepare_only:
        call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False)


if __name__ == "__main__":
    main()
