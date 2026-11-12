from django.http import JsonResponse

from cliente.models import Cliente
from mascota.models import Mascota
from pagInicio.api import ApiProblem, api_endpoint, request_data

from . import services
from .forms import ConfirmarAdopcionForm, RegistroAdopcionForm, EvaluacionForm
from .models import Adopcion, EvaluacionAdopcion


def _nombre(cliente):
    return f"{cliente.nombre} {cliente.apellido}".strip() if cliente else ""


def _validar(form):
    if not form.is_valid():
        raise ApiProblem("Revisa los campos de la adopción.", errors={key: list(value) for key, value in form.errors.items()})
    return form.cleaned_data


def _transicion(func, **kwargs):
    try:
        return func(**kwargs)
    except services.AdoptionConflict as exc:
        raise ApiProblem(str(exc), status=409) from exc


@api_endpoint("GET")
def datos(request):
    disponibles = Mascota.objects.select_related("cliente_id").filter(
        cliente_id__estado="Activo"
    ).exclude(adopciones__activa=True).order_by("nombre", "pk")
    return JsonResponse({
        "mascotas": [{"id": m.pk, "nombre": m.nombre, "especie": m.especie,
                      "cliente_id": m.cliente_id_id, "cliente_nombre": _nombre(m.cliente_id)} for m in disponibles],
        "clientes": [{"id": c.pk, "nombre": _nombre(c)} for c in Cliente.objects.filter(estado="Activo").order_by("nombre", "apellido", "pk")],
        "responsables": [{"id": e.pk, "nombre": str(e)} for e in services.responsables()],
    })


@api_endpoint("GET")
def listar(request):
    queryset = Adopcion.objects.select_related("mascota", "cliente_origen", "cliente_adoptante", "responsable")
    estado = request.GET.get("estado")
    if estado:
        if estado not in Adopcion.Estado.values:
            raise ApiProblem("Estado de adopción no válido.")
        queryset = queryset.filter(estado=estado)
    return JsonResponse({"adopciones": [{
        "id": a.pk, "mascota_id": a.mascota_id, "mascota_nombre": a.mascota.nombre,
        "especie": a.mascota.especie, "cliente_origen_id": a.cliente_origen_id,
        "cliente_origen": _nombre(a.cliente_origen), "cliente_adoptante_id": a.cliente_adoptante_id,
        "cliente_adoptante": _nombre(a.cliente_adoptante), "responsable_id": a.responsable_id,
        "responsable": str(a.responsable), "estado": a.estado, "motivo": a.motivo,
        "observaciones": a.observaciones, "observaciones_adopcion": a.observaciones_adopcion,
        "evaluacion_id": a.evaluacion_aprobada_id,
        "fecha_registro": a.fecha_registro.isoformat(),
        "fecha_adopcion": a.fecha_adopcion.isoformat() if a.fecha_adopcion else None,
        "fecha_cierre": a.fecha_cierre.isoformat() if a.fecha_cierre else None,
    } for a in queryset]})


@api_endpoint("POST")
def registrar(request):
    data = _validar(RegistroAdopcionForm(request_data(request)))
    adopcion = _transicion(services.registrar, **data, usuario=request.user)
    return JsonResponse({"status": "ok", "message": "Mascota registrada en adopción.", "id": adopcion.pk}, status=201)


@api_endpoint("POST")
def adoptar(request, adopcion_id):
    data = _validar(ConfirmarAdopcionForm(request_data(request)))
    adopcion = _transicion(services.adoptar, adopcion_id=adopcion_id, **data, usuario=request.user)
    return JsonResponse({"status": "ok", "message": "Adopción completada. La mascota ya pertenece al cliente adoptante.", "id": adopcion.pk})


@api_endpoint("POST")
def cancelar(request, adopcion_id):
    adopcion = _transicion(services.cancelar, adopcion_id=adopcion_id, usuario=request.user)
    return JsonResponse({"status": "ok", "message": "Publicación cancelada; la mascota conserva su propietario.", "id": adopcion.pk})


def _evaluacion(evaluacion):
    return {
        "id": evaluacion.pk, "cliente_id": evaluacion.cliente_id,
        "cliente_nombre": _nombre(evaluacion.cliente), "puntaje": evaluacion.puntaje,
        "aprobada": evaluacion.aprobada, "desglose": evaluacion.desglose,
        "respuestas": evaluacion.respuestas, "version": evaluacion.version,
        "fecha": evaluacion.fecha.isoformat(),
    }


@api_endpoint("POST")
def evaluar(request, adopcion_id):
    data = _validar(EvaluacionForm(request_data(request)))
    evaluacion = _transicion(services.evaluar, adopcion_id=adopcion_id, usuario=request.user, **data)
    return JsonResponse({"status": "ok", "message": "Evaluación guardada.", "evaluacion": _evaluacion(evaluacion)}, status=201)


@api_endpoint("GET")
def evaluaciones(request, adopcion_id):
    adopcion = Adopcion.objects.get(pk=adopcion_id)
    return JsonResponse({"evaluaciones": [_evaluacion(e) for e in adopcion.evaluaciones.select_related("cliente")]})
