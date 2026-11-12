"""Flujos de gestión de VetCare con validación y escrituras atómicas."""
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from cita.models import Cita
from cliente.models import Cliente
from empl_veterinario.models import Veterinario
from factura.models import Factura
from historial_de_vacunas.models import Historial_de_Vacunas
from mascota.models import Mascota
from tratamiento.models import Tratamiento
from .api import ApiProblem, api_endpoint, positive_id, request_data
from .forms import (PAYMENT_STATES, CitaForm, ClienteForm, FacturaForm,
                    MascotaForm, TratamientoForm, VacunaForm, validated)


def _ok(message, **extra):
    return JsonResponse({"status": "ok", "message": message, **extra})


def _full_name(person):
    return f"{person.nombre} {person.apellido}".strip()


def _client_data(client):
    return {"id": client.pk, "nombre": client.nombre, "apellido": client.apellido,
            "direccion": client.direccion, "email": client.email,
            "telefono": client.telefono, "estado": client.estado}


def _pet_data(pet):
    client = pet.cliente_id
    return {"id": pet.pk, "id_mascota": pet.pk, "mascota": pet.nombre,
            "nombre": pet.nombre, "especie": pet.especie, "raza": pet.raza,
            "edad": pet.edad, "peso": float(pet.peso), "cliente_id": client.pk,
            "cliente": _full_name(client), "cliente_nombre": client.nombre,
            "cliente_apellido": client.apellido, "email": client.email,
            "telefono": client.telefono, "cliente_estado": client.estado}


def _appointment_client(appointment):
    return getattr(appointment, "cliente_id", None) or appointment.mascota_id.cliente_id


def _appointments():
    return Cita.objects.select_related("mascota_id__cliente_id", "veterinario_id__id_veterinario", "cliente_id")


def _appointment_data(appointment):
    client = _appointment_client(appointment)
    return {"id": appointment.pk, "fecha": appointment.fecha.isoformat(),
            "hora": appointment.hora.strftime("%H:%M"), "motivo": appointment.motivo,
            "estado": appointment.estado, "mascota_id": appointment.mascota_id_id,
            "mascota": appointment.mascota_id.nombre, "cliente_id": client.pk,
            "cliente": _full_name(client), "veterinario_id": appointment.veterinario_id_id,
            "veterinario": _full_name(appointment.veterinario_id.id_veterinario)}


def _dashboard_data():
    today = timezone.localdate()
    appointments = _appointments().filter(fecha=today).order_by("hora", "pk")
    latest = Historial_de_Vacunas.objects.filter(
        mascota_id=OuterRef("mascota_id"), nombre_vacuna=OuterRef("nombre_vacuna")
    ).order_by("-fecha_aplic", "-pk").values("pk")[:1]
    due = Historial_de_Vacunas.objects.filter(
        pk=Subquery(latest), fecha_venc__lte=today + timedelta(days=30)
    ).count()
    return {"total_citas_hoy": appointments.exclude(estado="Cancelada").count(),
            "total_clientes_activos": Cliente.objects.filter(estado="Activo").count(),
            "total_vacunas_pendientes": due, "total_mascotas": Mascota.objects.count(),
            "total_citas": Cita.objects.count(), "citas": appointments}


@never_cache
@login_required(login_url="home-login")
def home(request):
    return render(request, "pagInicio/vet_dashboard.html", _dashboard_data())


@api_endpoint("GET")
def api_dashboard(request):
    data = _dashboard_data()
    data["citas_hoy"] = [_appointment_data(item) for item in data.pop("citas")]
    return JsonResponse({"status": "ok", **data})


@api_endpoint("GET")
def api_clientes(request):
    return JsonResponse({"status": "ok", "clientes": [
        _client_data(item) for item in Cliente.objects.order_by("nombre", "apellido", "pk")
    ]})


@api_endpoint("POST")
def crear_cliente(request):
    data = validated(ClienteForm, request_data(request))
    data["estado"] = data["estado"] or "Activo"
    with transaction.atomic():
        client = Cliente(**data)
        client.full_clean()
        client.save()
    return _ok("Cliente registrado correctamente.", cliente=_client_data(client), cliente_id=client.pk)


@api_endpoint("POST")
def editar_cliente(request):
    values = request_data(request)
    data = validated(ClienteForm, values)
    with transaction.atomic():
        client = Cliente.objects.select_for_update().get(pk=positive_id(values.get("cliente_id"), "cliente_id"))
        data["estado"] = data["estado"] or client.estado
        for key, value in data.items():
            setattr(client, key, value)
        client.full_clean()
        client.save()
    return _ok("Cliente actualizado correctamente.", cliente=_client_data(client))


@api_endpoint("GET")
def api_mascotas(request):
    pets = Mascota.objects.select_related("cliente_id").order_by("nombre", "pk")
    return JsonResponse({"status": "ok", "mascotas": [_pet_data(pet) for pet in pets]})


@api_endpoint("POST")
def registrar_cliente(request):
    values = request_data(request)
    pet_data = validated(MascotaForm, values)
    existing_id = values.get("cliente_id")
    client_data = None if existing_id else validated(ClienteForm, values)
    with transaction.atomic():
        if existing_id:
            client = Cliente.objects.select_for_update().get(pk=positive_id(existing_id, "cliente_id"))
        else:
            client_data["estado"] = client_data["estado"] or "Activo"
            client = Cliente(**client_data)
            client.full_clean()
            client.save()
        if client.estado != "Activo":
            raise ApiProblem("Selecciona un cliente activo para registrar la mascota.")
        pet = Mascota(nombre=pet_data.pop("nombreMascota"), cliente_id=client, **pet_data)
        pet.full_clean()
        pet.save()
    return _ok("Mascota registrada correctamente.", mascota_id=pet.pk, cliente_id=client.pk)


@api_endpoint("GET")
def detalle_mascota(request, mascota_id):
    pet = Mascota.objects.select_related("cliente_id").get(pk=mascota_id)
    client = pet.cliente_id
    return JsonResponse({"status": "ok", "detalle": {
        "cliente_id": client.pk, "cliente_nombre": client.nombre,
        "cliente_apellido": client.apellido, "cliente_direccion": client.direccion,
        "cliente_email": client.email, "cliente_telefono": client.telefono,
        "cliente_estado": client.estado, "mascota_id": pet.pk,
        "mascota_nombre": pet.nombre, "mascota_especie": pet.especie,
        "mascota_raza": pet.raza, "mascota_edad": pet.edad, "mascota_peso": float(pet.peso),
    }})


@api_endpoint("POST")
def editar_registro(request):
    values = request_data(request)
    client_data = validated(ClienteForm, values)
    pet_data = validated(MascotaForm, values)
    with transaction.atomic():
        pet = Mascota.objects.select_for_update().get(pk=positive_id(values.get("mascotaId"), "mascotaId"))
        client_id = positive_id(values.get("clienteId"), "clienteId")
        if pet.cliente_id_id != client_id:
            raise ApiProblem("La mascota ya no pertenece a ese cliente. Actualiza el registro.", 409)
        client = Cliente.objects.select_for_update().get(pk=client_id)
        client_data["estado"] = client_data["estado"] or client.estado
        for key, value in client_data.items():
            setattr(client, key, value)
        client.full_clean()
        pet.nombre = pet_data.pop("nombreMascota")
        for key, value in pet_data.items():
            setattr(pet, key, value)
        pet.full_clean()
        client.save()
        pet.save()
    return _ok("Registro actualizado correctamente.")


@api_endpoint("DELETE")
def eliminar_registro(request, mascota_id):
    with transaction.atomic():
        pet = Mascota.objects.select_for_update().get(pk=mascota_id)
        if Cita.objects.filter(mascota_id=pet).exists() or Historial_de_Vacunas.objects.filter(mascota_id=pet).exists():
            raise ApiProblem("La mascota tiene historial clínico o citas. No se puede eliminar.", 409)
        pet.delete()
    return _ok("Mascota eliminada. Se conserva el registro del cliente.", citas_eliminadas=0)


def _ensure_slot(appointment, exclude_id=None):
    if appointment.estado == "Cancelada":
        return
    conflicts = Cita.objects.filter(fecha=appointment.fecha, hora=appointment.hora).exclude(estado="Cancelada")
    if exclude_id:
        conflicts = conflicts.exclude(pk=exclude_id)
    if conflicts.filter(Q(veterinario_id=appointment.veterinario_id) | Q(mascota_id=appointment.mascota_id)).exists():
        raise ApiProblem("El veterinario o la mascota ya tiene una cita en ese horario.", 409)


@api_endpoint("POST")
def registrar_citas(request):
    data = validated(CitaForm, request_data(request))
    with transaction.atomic():
        vet = Veterinario.objects.select_for_update().get(pk=data.pop("veterinario"))
        pet = Mascota.objects.select_for_update().select_related("cliente_id").get(pk=data.pop("mascota"))
        if pet.cliente_id.estado != "Activo":
            raise ApiProblem("La mascota debe pertenecer a un cliente activo.")
        data["estado"] = data["estado"] or "Programada"
        if data["estado"] == "Atendida" and data["fecha"] > timezone.localdate():
            raise ApiProblem("Una cita futura no puede marcarse como atendida.")
        appointment = Cita(mascota_id=pet, veterinario_id=vet, **data)
        appointment.cliente_id = pet.cliente_id
        _ensure_slot(appointment)
        appointment.full_clean()
        appointment.save()
    return _ok("Cita creada correctamente.", cita_id=appointment.pk)


@api_endpoint("GET")
def api_citas(request):
    return JsonResponse({"status": "ok", "citas": [
        _appointment_data(item) for item in _appointments().order_by("-fecha", "hora", "pk")
    ]})


@api_endpoint("POST")
def actualizar_estado_cita(request, cita_id=None):
    data = request_data(request)
    appointment_id = positive_id(cita_id or data.get("cita_id"), "cita_id")
    state = data.get("estado")
    if state not in dict(Cita.ESTADOS):
        raise ApiProblem("Selecciona un estado de cita válido.")
    appointment = Cita.objects.get(pk=appointment_id)
    with transaction.atomic():
        Veterinario.objects.select_for_update().get(pk=appointment.veterinario_id_id)
        Mascota.objects.select_for_update().get(pk=appointment.mascota_id_id)
        appointment = Cita.objects.select_for_update().get(pk=appointment_id)
        if state == "Atendida" and appointment.fecha > timezone.localdate():
            raise ApiProblem("Una cita futura no puede marcarse como atendida.")
        if state == "Cancelada" and (appointment.tratamiento_set.exists() or appointment.factura_set.exclude(estado_pago="Cancelada").exists()):
            raise ApiProblem("La cita tiene tratamientos o facturas vigentes y no puede cancelarse.", 409)
        appointment.estado = state
        _ensure_slot(appointment, exclude_id=appointment.pk)
        appointment.save(update_fields=["estado"])
    return _ok("Estado de la cita actualizado.")


@api_endpoint("GET")
def cargar_datos(request):
    pets = Mascota.objects.filter(cliente_id__estado="Activo").select_related("cliente_id").order_by("nombre", "pk")
    vets = Veterinario.objects.select_related("id_veterinario").order_by("id_veterinario__nombre")
    return JsonResponse({"status": "ok", "mascotas": [_pet_data(pet) for pet in pets],
                         "veterinarios": [{"id": vet.pk, "nombre": vet.id_veterinario.nombre,
                                           "apellido": vet.id_veterinario.apellido,
                                           "especialidad": vet.especialidad} for vet in vets]})


@api_endpoint("GET")
def api_mascotas_selector(request):
    pets = Mascota.objects.select_related("cliente_id").order_by("nombre", "pk")
    return JsonResponse({"status": "ok", "mascotas": [_pet_data(pet) for pet in pets]})


@api_endpoint("GET")
def api_vacunas_mascota(request, mascota_id):
    pet = Mascota.objects.get(pk=mascota_id)
    vaccines = Historial_de_Vacunas.objects.filter(mascota_id=pet).order_by("-fecha_aplic", "-pk")
    today = timezone.localdate()
    return JsonResponse({"status": "ok", "mascota": {"nombre": pet.nombre, "especie": pet.especie, "raza": pet.raza},
                         "vacunas": [{"id": item.pk, "nombre": item.nombre_vacuna,
                                      "fecha_aplicacion": item.fecha_aplic.isoformat(),
                                      "fecha_vencimiento": item.fecha_venc.isoformat(), "lote": item.lote,
                                      "dias_para_vencer": (item.fecha_venc - today).days} for item in vaccines]})


@api_endpoint("POST")
def registrar_vacuna(request):
    data = validated(VacunaForm, request_data(request))
    with transaction.atomic():
        pet = Mascota.objects.select_for_update().get(pk=data["mascota_id"])
        if Historial_de_Vacunas.objects.filter(mascota_id=pet, nombre_vacuna=data["nombre_vacuna"],
                                               fecha_aplic=data["fecha_aplicacion"], lote=data["lote"]).exists():
            raise ApiProblem("Esa aplicación de la vacuna ya está registrada.", 409)
        vaccine = Historial_de_Vacunas(mascota_id=pet, nombre_vacuna=data["nombre_vacuna"],
                                      fecha_aplic=data["fecha_aplicacion"], fecha_venc=data["fecha_vencimiento"], lote=data["lote"])
        vaccine.full_clean()
        vaccine.save()
    return _ok("Vacuna registrada correctamente.", vacuna_id=vaccine.pk)


@api_endpoint("GET")
def api_tratamientos_mascota(request, mascota_id):
    pet = Mascota.objects.get(pk=mascota_id)
    treatments = Tratamiento.objects.filter(cita_id__mascota_id=pet).select_related("cita_id").order_by("-fecha_inicio", "-pk")
    return JsonResponse({"status": "ok", "mascota": {"nombre": pet.nombre, "especie": pet.especie, "raza": pet.raza},
                         "tratamientos": [{"id": item.pk, "descripcion": item.descripcion, "medicamento": item.medicamento,
                                            "dosis": item.dosis, "duracion": item.duracion, "fecha_inicio": item.fecha_inicio.isoformat(),
                                            "cita_fecha": item.cita_id.fecha.isoformat(), "cita_motivo": item.cita_id.motivo}
                                           for item in treatments]})


@api_endpoint("POST")
def registrar_tratamiento(request):
    data = validated(TratamientoForm, request_data(request))
    with transaction.atomic():
        appointment = Cita.objects.select_for_update().get(pk=data.pop("cita_id"))
        if appointment.estado == "Cancelada":
            raise ApiProblem("No se puede registrar un tratamiento para una cita cancelada.", 409)
        if data["fecha_inicio"] < appointment.fecha:
            raise ApiProblem("El tratamiento no puede empezar antes de la cita asociada.")
        treatment = Tratamiento(cita_id=appointment, **data)
        treatment.full_clean()
        treatment.save()
    return _ok("Tratamiento registrado correctamente.", tratamiento_id=treatment.pk)


@api_endpoint("GET")
def citas_mascota(request, mascota_id):
    pet = Mascota.objects.get(pk=mascota_id)
    return JsonResponse({"status": "ok", "citas": [
        _appointment_data(item) for item in _appointments().filter(mascota_id=pet).order_by("-fecha", "-hora")
    ]})


def _financial_permission(request):
    if not request.user.is_staff:
        raise ApiProblem("Solo el personal autorizado puede modificar facturas.", 403)


def _invoices():
    return Factura.objects.select_related("cliente_id", "cita_id__mascota_id", "administrador_id")


def _invoice_data(invoice):
    return {"id": invoice.pk, "fecha": invoice.fecha_emision.isoformat(), "cliente": _full_name(invoice.cliente_id),
            "monto": float(invoice.monto_total), "estado": invoice.estado_pago, "cita_motivo": invoice.cita_id.motivo,
            "administrador": invoice.administrador_id.get_full_name() or invoice.administrador_id.get_username()}


@api_endpoint("GET")
def api_resumen_facturas(request):
    invoices = Factura.objects.all()
    paid = invoices.filter(estado_pago="Pagada")
    pending = invoices.filter(estado_pago="Pendiente")
    return JsonResponse({"status": "ok", "resumen": {
        "total_facturas": invoices.count(), "facturas_pagadas": paid.count(), "facturas_pendientes": pending.count(),
        "total_ingresos": float(paid.aggregate(total=Sum("monto_total"))["total"] or Decimal("0.00")),
        "total_pendiente": float(pending.aggregate(total=Sum("monto_total"))["total"] or Decimal("0.00")),
    }})


@api_endpoint("GET")
def api_listar_facturas(request):
    return JsonResponse({"status": "ok", "facturas": [
        _invoice_data(invoice) for invoice in _invoices().order_by("-fecha_emision", "-pk")
    ]})


@api_endpoint("GET")
def api_detalle_factura(request, factura_id):
    invoice = _invoices().get(pk=factura_id)
    return JsonResponse({"status": "ok", "detalle": {
        "id": invoice.pk, "fecha_emision": invoice.fecha_emision.isoformat(), "monto_total": float(invoice.monto_total),
        "estado_pago": invoice.estado_pago, "cliente_nombre": _full_name(invoice.cliente_id),
        "cliente_email": invoice.cliente_id.email, "cliente_telefono": invoice.cliente_id.telefono,
        "cita_fecha": invoice.cita_id.fecha.isoformat(), "cita_motivo": invoice.cita_id.motivo,
        "mascota_nombre": invoice.cita_id.mascota_id.nombre,
        "administrador": invoice.administrador_id.get_full_name() or invoice.administrador_id.get_username(),
    }})


@api_endpoint("POST")
def registrar_factura(request):
    _financial_permission(request)
    data = validated(FacturaForm, request_data(request))
    if data["administrador_id"] and data["administrador_id"] != request.user.pk:
        raise ApiProblem("El administrador de la factura debe ser el usuario de la sesión.")
    with transaction.atomic():
        appointment = Cita.objects.select_for_update().select_related("mascota_id__cliente_id").get(pk=data["cita_id"])
        client = Cliente.objects.get(pk=data["cliente_id"])
        if _appointment_client(appointment).pk != client.pk:
            raise ApiProblem("El cliente no corresponde a la cita seleccionada.")
        if appointment.estado == "Cancelada":
            raise ApiProblem("No se puede facturar una cita cancelada.", 409)
        if data["estado_pago"] != "Cancelada" and Factura.objects.filter(cita_id=appointment).exclude(estado_pago="Cancelada").exists():
            raise ApiProblem("La cita ya tiene una factura vigente.", 409)
        invoice = Factura(fecha_emision=data["fecha_emision"], monto_total=data["monto_total"],
                          estado_pago=data["estado_pago"], cita_id=appointment,
                          cliente_id=client, administrador_id=request.user)
        invoice.full_clean()
        invoice.save()
    return _ok("Factura registrada correctamente.", factura_id=invoice.pk)


@api_endpoint("POST")
def actualizar_estado_factura(request):
    _financial_permission(request)
    data = request_data(request)
    state = data.get("estado_pago")
    if state not in dict(PAYMENT_STATES):
        raise ApiProblem("Selecciona un estado de pago válido.")
    invoice_id = positive_id(data.get("factura_id"), "factura_id")
    invoice = Factura.objects.get(pk=invoice_id)
    with transaction.atomic():
        appointment = Cita.objects.select_for_update().get(pk=invoice.cita_id_id)
        if state != "Cancelada" and appointment.estado == "Cancelada":
            raise ApiProblem("No se puede reactivar una factura de una cita cancelada.", 409)
        invoice = Factura.objects.select_for_update().get(pk=invoice_id)
        if state != "Cancelada" and Factura.objects.filter(cita_id=invoice.cita_id).exclude(pk=invoice.pk).exclude(estado_pago="Cancelada").exists():
            raise ApiProblem("La cita ya tiene otra factura vigente.", 409)
        invoice.estado_pago = state
        invoice.save(update_fields=["estado_pago"])
    return _ok("Estado de pago actualizado.")


@api_endpoint("GET")
def api_datos_factura(request):
    appointments = _appointments().exclude(estado="Cancelada").exclude(
        factura__estado_pago__in=["Pagada", "Pendiente"]).order_by("-fecha", "hora")
    data = []
    for appointment in appointments:
        client = _appointment_client(appointment)
        data.append({"id": appointment.pk, "fecha": appointment.fecha.isoformat(), "motivo": appointment.motivo,
                     "cliente_id": client.pk, "cliente_nombre": _full_name(client), "mascota": appointment.mascota_id.nombre})
    administrators = []
    if request.user.is_staff:
        administrators.append({"id": request.user.pk, "nombre": request.user.get_full_name() or request.user.get_username()})
    return JsonResponse({"status": "ok", "citas": data, "administradores": administrators})

