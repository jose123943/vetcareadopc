"""Carga del entorno y validación de la conexión MySQL sin exponer secretos."""

import ipaddress
import re

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


def load_project_env(base_dir):
    # Solo se lee el .env junto a manage.py. El entorno del proceso tiene prioridad.
    # No expandir ${...}: puede ser parte de una contraseña o una referencia
    # de Railway que debe copiarse ya resuelta desde su panel.
    load_dotenv(base_dir / ".env", override=False, interpolate=False, encoding="utf-8-sig")


def database_from_environment(environ):
    keys = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")
    values = {key: environ.get(key, "") for key in keys}
    for key in keys:
        if key != "DB_PASSWORD":
            values[key] = values[key].strip()

    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "Faltan variables de conexión: " + ", ".join(missing)
            + ". Completa el .env junto a manage.py. Para Railway desde Windows, "
            "usa el dominio y el puerto públicos del TCP Proxy. Consulta README.md."
        )

    unresolved = [
        key for key, value in values.items()
        if key != "DB_PASSWORD" and "${" in value
    ]
    if re.fullmatch(r"\$\{\{[^{}]+\}\}", values["DB_PASSWORD"]):
        unresolved.append("DB_PASSWORD")
    if unresolved:
        raise ImproperlyConfigured(
            "Hay referencias sin resolver en: " + ", ".join(unresolved)
            + ". Copia los valores reales de Railway, no expresiones ${...} "
            "o ${{...}}. DB_HOST debe contener solo el dominio o la IP."
        )

    host = values["DB_HOST"]
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels = host.removesuffix(".").split(".")
        valid_host = len(host) <= 253 and all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        )
        if not valid_host:
            raise ImproperlyConfigured(
                "DB_HOST no es un dominio o una IP válidos. No pegues una URL, "
                "credenciales, llaves ni el puerto aquí; usa DB_USER, DB_PASSWORD "
                "y DB_PORT por separado."
            ) from None

    if host.lower().rstrip(".").endswith(".railway.internal") and not environ.get(
        "RAILWAY_ENVIRONMENT_ID"
    ):
        raise ImproperlyConfigured(
            "DB_HOST usa la red privada de Railway, inaccesible desde el entorno "
            "local. Configura el dominio público del TCP Proxy y su puerto externo."
        )

    port = values["DB_PORT"]
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise ImproperlyConfigured("DB_PORT debe ser un número entre 1 y 65535.")

    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": values["DB_NAME"],
        "USER": values["DB_USER"],
        "PASSWORD": values["DB_PASSWORD"],
        "HOST": host,
        "PORT": int(port),
        "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 15},
        "CONN_MAX_AGE": 0,
    }
