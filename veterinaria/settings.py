
"""
Configuración de Django para VetCare.
Django 5.2 LTS

Base de datos: MySQL en Railway
Entorno: Desarrollo local
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

from .config import database_from_environment, load_project_env


# ==========================================
# 1. RUTAS DEL PROYECTO
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables desde el archivo .env
load_project_env(BASE_DIR)


# ==========================================
# 2. SEGURIDAD
# ==========================================

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Falta SECRET_KEY en el archivo .env"
    )

DEBUG = os.getenv(
    "DEBUG", "True"
).lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]

SESSION_EXPIRE_AT_BROWSER_CLOSE = True


# ==========================================
# 3. APLICACIONES INSTALADAS
# ==========================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Aplicaciones de VetCare
    "administrador",
    "cita",
    "cliente",
    "empl_veterinario",
    "empleado",
    "factura",
    "historial_de_vacunas",
    "mascota",
    "tratamiento",
    "login",
    "pagInicio",
    "adopcion",
]


# ==========================================
# 4. MIDDLEWARE
# ==========================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ==========================================
# 5. CONFIGURACIÓN PRINCIPAL
# ==========================================

ROOT_URLCONF = "veterinaria.urls"

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth."
                    "context_processors.auth"
                ),
                (
                    "django.contrib.messages."
                    "context_processors.messages"
                ),
            ],
        },
    },
]

WSGI_APPLICATION = "veterinaria.wsgi.application"


# ==========================================
# 6. BASE DE DATOS MYSQL - RAILWAY
# ==========================================

DATABASES = {
    "default": database_from_environment(os.environ),
}


# ==========================================
# 7. VALIDACIÓN DE CONTRASEÑAS
# ==========================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ==========================================
# 8. IDIOMA Y ZONA HORARIA
# ==========================================

LANGUAGE_CODE = "es-co"

TIME_ZONE = "America/Bogota"

USE_I18N = True

USE_TZ = True


# ==========================================
# 9. ARCHIVOS ESTÁTICOS
# ==========================================

STATIC_URL = "/static/"


# ==========================================
# 10. CLAVES PRIMARIAS
# ==========================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
