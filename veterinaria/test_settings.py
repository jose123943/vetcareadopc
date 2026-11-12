"""Pruebas aisladas: no lee .env y nunca usa la base de Railway."""

import os
import runpy
from unittest.mock import patch


_test_environment = {
    "SECRET_KEY": "vetcare-tests-only-not-for-deployment",
    "DEBUG": "False",
    "ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
    "DB_NAME": "unused_test_configuration",
    "DB_USER": "unused",
    "DB_PASSWORD": "unused",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
}

# Reutilizar apps, middleware y plantillas sin duplicar la configuración ni
# cargar credenciales locales. El entorno del proceso se restaura al terminar.
with patch.dict(os.environ, _test_environment), patch("veterinaria.config.load_project_env"):
    _base_settings = runpy.run_module("veterinaria.settings")

globals().update({key: value for key, value in _base_settings.items() if key.isupper()})

SECRET_KEY = _test_environment["SECRET_KEY"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {"NAME": ":memory:"},
    }
}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
