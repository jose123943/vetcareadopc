"""Contrato común de las API internas: sesión, métodos y errores seguros."""

from functools import wraps
import json
import logging

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.utils.cache import patch_cache_control


logger = logging.getLogger(__name__)


class ApiProblem(Exception):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors


def _error(message, status, errors=None):
    payload = {"status": "error", "message": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def api_endpoint(*methods):
    """No sustituye el middleware CSRF: todas las escrituras siguen protegidas."""
    allowed = tuple(method.upper() for method in methods)

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                response = _error("La sesión terminó. Inicia sesión de nuevo.", 401)
            elif request.method not in allowed:
                response = _error("Método no permitido.", 405)
                response["Allow"] = ", ".join(allowed)
            else:
                try:
                    response = view(request, *args, **kwargs)
                except ApiProblem as exc:
                    response = _error(exc.message, exc.status, exc.errors)
                except ValidationError as exc:
                    errors = exc.message_dict if hasattr(exc, "message_dict") else {"datos": exc.messages}
                    response = _error("Revisa los datos del formulario.", 400, errors)
                except ObjectDoesNotExist:
                    response = _error("El registro solicitado no existe.", 404)
                except ProtectedError:
                    response = _error("El registro tiene historial relacionado y no puede eliminarse.", 409)
                except IntegrityError:
                    response = _error("La operación entra en conflicto con otro registro. Actualiza e inténtalo de nuevo.", 409)
                except DatabaseError:
                    logger.exception("No se pudo completar una operación de base de datos en %s", request.path)
                    response = _error("No se pudo acceder a la base de datos. Inténtalo de nuevo más tarde.", 503)
                except Exception:
                    logger.exception("Error inesperado en %s", request.path)
                    response = _error("No se pudo completar la operación. Contacta al administrador.", 500)
            patch_cache_control(response, private=True, no_store=True, no_cache=True)
            return response

        return wrapped

    return decorate


def request_data(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            raise ApiProblem("El contenido JSON no es válido.") from None
        if not isinstance(data, dict):
            raise ApiProblem("El contenido debe ser un objeto JSON.")
        return data
    return request.POST


def positive_id(value, field="id"):
    text = str(value or "").strip()
    if len(text) > 19 or not text.isascii() or not text.isdigit() or not 0 < int(text) <= 9223372036854775807:
        raise ValidationError({field: "Selecciona un registro válido."})
    return int(text)
