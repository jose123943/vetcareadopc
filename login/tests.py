from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from .views import login_view


class LoginCsrfTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_login_form_includes_token_and_cannot_be_cached(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'id="login-form"')
        self.assertContains(response, '/static/login/js/login.js')
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_authenticated_get_redirects_to_dashboard(self):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        response = login_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/inicio/")
        self.assertIn("no-store", response.headers["Cache-Control"])

    @patch("login.views.authenticate", return_value=None)
    def test_current_token_reaches_authentication(self, authenticate):
        self.client.get("/")
        response = self.client.post("/", {
            "username": "test-only-user",
            "password": "test-only-password",
            "csrfmiddlewaretoken": self.client.cookies[settings.CSRF_COOKIE_NAME].value,
        })
        self.assertEqual(response.status_code, 200)
        authenticate.assert_called_once()
        self.assertIn("no-store", response.headers["Cache-Control"])

    @patch("login.views.authenticate")
    def test_stale_token_is_still_rejected_before_authentication(self, authenticate):
        self.client.get("/")
        old_token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        other_browser = Client(enforce_csrf_checks=True)
        other_browser.get("/")
        self.client.cookies[settings.CSRF_COOKIE_NAME] = (
            other_browser.cookies[settings.CSRF_COOKIE_NAME].value
        )
        response = self.client.post("/", {
            "username": "test-only-user",
            "password": "test-only-password",
            "csrfmiddlewaretoken": old_token,
        })
        self.assertEqual(response.status_code, 403)
        authenticate.assert_not_called()


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
class LogoutTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get("/")
        self.user = get_user_model()(pk=123, username="logout-test-user")
        # Solo se simula la búsqueda del usuario; middleware, sesión y logout son reales.
        self.enterContext(patch(
            "django.contrib.auth.backends.ModelBackend.get_user", return_value=self.user
        ))
        session = SessionStore()
        session[SESSION_KEY] = str(self.user.pk)
        session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        session[HASH_SESSION_KEY] = self.user.get_session_auth_hash()
        session["test_session_value"] = "must-be-removed"
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_logout_requires_post(self):
        response = self.client.get("/logout/")
        self.assertEqual(response.status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_logout_rejects_post_without_csrf_token(self):
        response = self.client.post("/logout/")
        self.assertEqual(response.status_code, 403)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_logout_flushes_session_and_dashboard_requires_login_again(self):
        response = self.client.post("/logout/", {
            "csrfmiddlewaretoken": self.client.cookies[settings.CSRF_COOKIE_NAME].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(dict(self.client.session), {})
        dashboard = self.client.get("/inicio/")
        self.assertEqual(dashboard.status_code, 302)
        self.assertEqual(dashboard.url, "/?next=/inicio/")
        self.assertIn("no-store", dashboard.headers["Cache-Control"])
