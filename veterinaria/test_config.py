"""Regresiones de configuración; no requieren conexión ni una base de pruebas."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured

from veterinaria.config import database_from_environment, load_project_env


class DatabaseConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "DB_NAME": "vetcare_test",
            "DB_USER": "test_user",
            "DB_PASSWORD": "test-only-password",
            "DB_HOST": "example.proxy.rlwy.net",
            "DB_PORT": "15432",
        }

    def test_separate_values_keep_password_literal(self):
        self.env["DB_PASSWORD"] = "  p@ss:#/?${VALUE}%!  "
        db = database_from_environment(self.env)
        self.assertEqual(db["PASSWORD"], self.env["DB_PASSWORD"])
        self.assertEqual(db["PORT"], 15432)
        self.assertEqual(db["ENGINE"], "django.db.backends.mysql")

    def test_original_railway_template_is_rejected(self):
        self.env["DB_HOST"] = (
            "${{MYSQLUSER}}:${{MYSQLPASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:"
            "${{RAILWAY_TCP_PROXY_PORT}}/${{MYSQLDATABASE}}"
        )
        with self.assertRaisesRegex(ImproperlyConfigured, "referencias sin resolver"):
            database_from_environment(self.env)

    def test_invalid_hosts_do_not_leak_embedded_credentials(self):
        for host in [
            "}:}@}:}/}",
            "mysql://test_user:secret-marker@example.com:1234/database",
            "example.com:1234", "example.com/path", "bad host", "-bad.example",
            "example.com..",
        ]:
            with self.subTest(host=host):
                self.env["DB_HOST"] = host
                with self.assertRaises(ImproperlyConfigured) as caught:
                    database_from_environment(self.env)
                self.assertNotIn(host, str(caught.exception))
                self.assertNotIn("secret-marker", str(caught.exception))

    def test_private_railway_host_requires_railway_environment(self):
        self.env["DB_HOST"] = "mysql.railway.internal"
        with self.assertRaisesRegex(ImproperlyConfigured, "red privada"):
            database_from_environment(self.env)
        self.env["RAILWAY_ENVIRONMENT_ID"] = "test-environment"
        self.assertEqual(database_from_environment(self.env)["HOST"], "mysql.railway.internal")

    def test_local_hosts_and_ip_addresses_are_supported(self):
        for host in ["localhost", "127.0.0.1", "::1"]:
            with self.subTest(host=host):
                self.env["DB_HOST"] = host
                self.assertEqual(database_from_environment(self.env)["HOST"], host)

    def test_missing_variables_are_named(self):
        for key in self.env:
            with self.subTest(key=key):
                env = {**self.env, key: ""}
                with self.assertRaisesRegex(ImproperlyConfigured, key):
                    database_from_environment(env)

    def test_port_is_required_even_when_absent(self):
        del self.env["DB_PORT"]
        with self.assertRaisesRegex(ImproperlyConfigured, "DB_PORT"):
            database_from_environment(self.env)

    def test_invalid_ports_are_rejected(self):
        for port in ["0", "65536", "-1", "3306.0", "abc", "${{MYSQLPORT}}"]:
            with self.subTest(port=port):
                self.env["DB_PORT"] = port
                with self.assertRaisesRegex(ImproperlyConfigured, "DB_PORT"):
                    database_from_environment(self.env)

    def test_password_reference_is_rejected(self):
        self.env["DB_PASSWORD"] = "${{MYSQLPASSWORD}}"
        with self.assertRaisesRegex(ImproperlyConfigured, "DB_PASSWORD"):
            database_from_environment(self.env)


class EnvironmentLoadingTests(unittest.TestCase):
    def test_root_file_preserves_literals_bom_and_process_priority(self):
        # Crear con permisos heredados: Python 3.14 restringe los directorios
        # temporales de Windows y puede bloquear al proceso de un sandbox.
        base_dir = Path(__file__).resolve().parent / f".env-test-{uuid4().hex}"
        base_dir.mkdir()
        try:
            (base_dir / ".env").write_text(
                "DB_HOST=from-file.example\n"
                "DB_PASSWORD='p@ss#:${KEEP_THIS}/end'\n"
                "SECRET_KEY=local-test-key\n",
                encoding="utf-8-sig",
            )
            (base_dir / ".venv").mkdir()
            (base_dir / ".venv" / ".env").write_text("SECRET_KEY=wrong-file\n")
            with patch.dict(os.environ, {"DB_HOST": "from-process.example"}, clear=True):
                load_project_env(base_dir)
                self.assertEqual(os.environ["DB_HOST"], "from-process.example")
                self.assertEqual(os.environ["DB_PASSWORD"], "p@ss#:${KEEP_THIS}/end")
                self.assertEqual(os.environ["SECRET_KEY"], "local-test-key")
        finally:
            (base_dir / ".venv" / ".env").unlink(missing_ok=True)
            if (base_dir / ".venv").exists():
                (base_dir / ".venv").rmdir()
            (base_dir / ".env").unlink(missing_ok=True)
            base_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
