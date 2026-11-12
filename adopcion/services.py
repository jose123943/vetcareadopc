"""Las transiciones de adopción bloquean la mascota y conservan su historial."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from cliente.models import Cliente
from empleado.models import Empleado
from mascota.models import Mascota

from .models import Adopcion, EvaluacionAdopcion
from .evaluation import calcular


class AdoptionConflict(Exception):
    pass


def responsables():
    return Empleado.objects.filter(cargo__iexact="Encargado de adopciones").order_by("nombre", "apellido", "pk")


@transaction.atomic
def registrar(*, mascota_id, responsable_id, motivo, observaciones, usuario):
    mascota = Mascota.objects.select_for_update().get(pk=mascota_id)
    propietario = Cliente.objects.select_for_update().get(pk=mascota.cliente_id_id)
    if propietario.estado != "Activo":
        raise ValidationError("El propietario de la mascota debe ser un cliente activo.")
    responsable = responsables().get(pk=responsable_id)
    if Adopcion.objects.filter(mascota=mascota, activa=True).exists():
        raise AdoptionConflict("Esta mascota ya tiene una adopción disponible.")
    adopcion = Adopcion(
        mascota=mascota, cliente_origen=propietario, responsable=responsable,
        motivo=motivo, observaciones=observaciones, creado_por=usuario,
    )
    adopcion.full_clean()
    adopcion.save()
    return adopcion


def _bloquear(adopcion_id):
    # Mismo orden de bloqueos en todas las transiciones: mascota, luego adopción.
    mascota_id = Adopcion.objects.values_list("mascota_id", flat=True).get(pk=adopcion_id)
    mascota = Mascota.objects.select_for_update().get(pk=mascota_id)
    adopcion = Adopcion.objects.select_for_update().get(pk=adopcion_id)
    if adopcion.estado != Adopcion.Estado.DISPONIBLE:
        raise AdoptionConflict("Esta publicación ya fue adoptada o cancelada.")
    return mascota, adopcion


@transaction.atomic
def adoptar(*, adopcion_id, cliente_adoptante_id, evaluacion_id, observaciones, usuario):
    mascota, adopcion = _bloquear(adopcion_id)
    if mascota.cliente_id_id != adopcion.cliente_origen_id:
        raise AdoptionConflict("El propietario cambió desde la publicación. Cancela y registra una nueva adopción.")
    if cliente_adoptante_id == adopcion.cliente_origen_id:
        raise ValidationError("El adoptante debe ser un cliente distinto al propietario actual.")
    adoptante = Cliente.objects.select_for_update().get(pk=cliente_adoptante_id)
    if adoptante.estado != "Activo":
        raise ValidationError("El cliente adoptante debe estar activo.")
    evaluacion = EvaluacionAdopcion.objects.get(pk=evaluacion_id, adopcion=adopcion, cliente=adoptante)
    if not evaluacion.aprobada or evaluacion.puntaje <= 70:
        raise ValidationError("La adopción requiere una evaluación superior al 70%.")
    if EvaluacionAdopcion.objects.filter(adopcion=adopcion, cliente=adoptante, pk__gt=evaluacion.pk).exists():
        raise AdoptionConflict("Existe una evaluación más reciente para este cliente. Usa su resultado.")
    instante = timezone.now()
    adopcion.cliente_adoptante = adoptante
    adopcion.estado = Adopcion.Estado.ADOPTADA
    adopcion.activa = None
    adopcion.fecha_adopcion = instante
    adopcion.fecha_cierre = instante
    adopcion.cerrado_por = usuario
    adopcion.observaciones_adopcion = observaciones
    adopcion.evaluacion_aprobada = evaluacion
    adopcion.full_clean()
    # Ambas escrituras se confirman juntas; vacunas, citas y facturas no se borran.
    mascota.cliente_id = adoptante
    mascota.save(update_fields=["cliente_id"])
    adopcion.save()
    return adopcion


@transaction.atomic
def evaluar(*, adopcion_id, cliente_adoptante_id, usuario, **respuestas):
    mascota, adopcion = _bloquear(adopcion_id)
    if mascota.cliente_id_id != adopcion.cliente_origen_id:
        raise AdoptionConflict("El propietario cambió desde la publicación; registra una nueva adopción.")
    if cliente_adoptante_id == adopcion.cliente_origen_id:
        raise ValidationError("El adoptante debe ser otro cliente.")
    cliente = Cliente.objects.get(pk=cliente_adoptante_id, estado="Activo")
    puntaje, aprobada, desglose = calcular(respuestas)
    # Decimales como cadenas para conservar los importes exactos en el historial JSON.
    snapshot = {key: value if isinstance(value, bool) else str(value) for key, value in respuestas.items()}
    evaluacion = EvaluacionAdopcion(
        adopcion=adopcion, cliente=cliente, respuestas=snapshot, desglose=desglose,
        puntaje=puntaje, aprobada=aprobada, evaluado_por=usuario,
    )
    evaluacion.full_clean()
    evaluacion.save()
    return evaluacion


@transaction.atomic
def cancelar(*, adopcion_id, usuario):
    _, adopcion = _bloquear(adopcion_id)
    adopcion.estado = Adopcion.Estado.CANCELADA
    adopcion.activa = None
    adopcion.fecha_cierre = timezone.now()
    adopcion.cerrado_por = usuario
    adopcion.full_clean()
    adopcion.save()
    return adopcion
