from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.utils import timezone

from cita.models import Cita
from cliente.models import Cliente
from empleado.models import Empleado
from empl_veterinario.models import Veterinario
from factura.models import Factura
from historial_de_vacunas.models import Historial_de_Vacunas
from mascota.models import Mascota
from tratamiento.models import Tratamiento
from .urls import urlpatterns


class DashboardFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = get_user_model().objects.create_user(
            username="operator", password="test-password", is_staff=True)
        cls.other_operator = get_user_model().objects.create_user(
            username="other-operator", password="test-password", is_staff=True)
        cls.client_a = Cliente.objects.create(nombre="Ana", apellido="Prueba",
            direccion="Calle 1", email="ana@example.test", telefono="3000000000")
        cls.client_b = Cliente.objects.create(nombre="Luis", apellido="Prueba",
            direccion="Calle 2", email="luis@example.test", telefono="3000000001")
        cls.pet = Mascota.objects.create(nombre="Luna", especie="Perro", raza="Mestiza",
            edad=2, peso=Decimal("12.50"), cliente_id=cls.client_a)
        cls.pet_b = Mascota.objects.create(nombre="Sol", especie="Gato", raza="Mestiza",
            edad=3, peso=Decimal("4.50"), cliente_id=cls.client_b)
        employee = Empleado.objects.create(nombre="Veterinaria", apellido="Prueba", cargo="Veterinario")
        cls.vet = Veterinario.objects.create(id_veterinario=employee, especialidad="Medicina interna")

    def setUp(self):
        self.client.force_login(self.operator)
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)

    def appointment(self, **overrides):
        data = dict(fecha=self.today, hora="10:00", motivo="Control", estado="Programada",
                    mascota_id=self.pet, veterinario_id=self.vet, cliente_id=self.client_a)
        data.update(overrides)
        return Cita.objects.create(**data)

    def customer_payload(self, **overrides):
        data = dict(nombre="Nueva", apellido="Persona", direccion="Calle 3",
                    email="nueva@example.test", telefono="3000000002")
        data.update(overrides)
        return data

    def pet_payload(self, **overrides):
        data = dict(nombreMascota="Nube", especie="Perro", raza="Mestiza", edad="1", peso="3.50")
        data.update(overrides)
        return data

    def appointment_payload(self, **overrides):
        data = dict(fecha=self.tomorrow.isoformat(), hora="10:00", motivo="Control",
                    estado="Programada", mascota=self.pet.pk, veterinario=self.vet.pk)
        data.update(overrides)
        return data

    def invoice_payload(self, appointment, **overrides):
        data = dict(fecha_emision=self.today.isoformat(), monto_total="100.50",
                    estado_pago="Pendiente", cita_id=appointment.pk, cliente_id=self.client_a.pk)
        data.update(overrides)
        return data

    def test_every_api_rejects_unauthenticated_access(self):
        anonymous = Client()
        for url in urlpatterns:
            route = str(url.pattern)
            if not route.startswith("api/"):
                continue
            for parameter in ("mascota_id", "cita_id", "factura_id"):
                route = route.replace(f"<int:{parameter}>", "1")
            with self.subTest(route=route):
                response = anonymous.get("/inicio/" + route)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["status"], "error")

    def test_mutations_require_expected_method_and_csrf(self):
        self.assertEqual(self.client.get("/inicio/api/registrar/cliente/").status_code, 405)
        self.assertEqual(self.client.post("/inicio/api/clientes/").status_code, 405)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.operator)
        response = browser.post("/inicio/api/registrar/cliente/", self.customer_payload())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Cliente.objects.count(), 2)

    def test_create_customer_without_pet_and_reuse_customer(self):
        response = self.client.post("/inicio/api/registrar/cliente/", self.customer_payload())
        self.assertEqual(response.status_code, 200)
        customer_id = response.json()["cliente_id"]
        response = self.client.post("/inicio/api/registrar/cliente-mascota/",
            self.pet_payload(cliente_id=customer_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Cliente.objects.count(), 3)
        self.assertEqual(Mascota.objects.get(pk=response.json()["mascota_id"]).cliente_id_id, customer_id)

    def test_customer_validation_prevents_partial_records(self):
        response = self.client.post("/inicio/api/registrar/cliente-mascota/",
            {**self.customer_payload(email="invalid"), **self.pet_payload()})
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        self.assertEqual(Cliente.objects.count(), 2)
        self.assertEqual(Mascota.objects.count(), 2)

    def test_pet_nonfinite_negative_and_precision_values_are_rejected(self):
        for value in ("NaN", "Infinity", "-1", "500.01", "1.001"):
            with self.subTest(weight=value):
                response = self.client.post("/inicio/api/registrar/cliente-mascota/",
                    self.pet_payload(cliente_id=self.client_a.pk, peso=value))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Mascota.objects.count(), 2)

    def test_customer_and_pet_creation_roll_back_together(self):
        with patch("pagInicio.views.Mascota.save", side_effect=IntegrityError("private-database-details")):
            response = self.client.post("/inicio/api/registrar/cliente-mascota/",
                {**self.customer_payload(), **self.pet_payload()})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("private-database-details", response.content.decode())
        self.assertEqual(Cliente.objects.count(), 2)

    def test_edit_rejects_unrelated_customer_and_preserves_both(self):
        response = self.client.post("/inicio/api/editar-registro/", {
            **self.customer_payload(), **self.pet_payload(),
            "clienteId": self.client_b.pk, "mascotaId": self.pet.pk,
        })
        self.assertEqual(response.status_code, 409)
        self.client_b.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(self.client_b.nombre, "Luis")
        self.assertEqual(self.pet.cliente_id_id, self.client_a.pk)

    def test_edit_rolls_back_customer_if_pet_save_fails(self):
        with patch("pagInicio.views.Mascota.save", side_effect=IntegrityError("constraint")):
            response = self.client.post("/inicio/api/editar-registro/", {
                **self.customer_payload(), **self.pet_payload(),
                "clienteId": self.client_a.pk, "mascotaId": self.pet.pk,
            })
        self.assertEqual(response.status_code, 409)
        self.client_a.refresh_from_db()
        self.assertEqual(self.client_a.nombre, "Ana")

    def test_deleting_unused_pet_keeps_customer(self):
        response = self.client.delete(f"/inicio/api/eliminar-registro/{self.pet.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Mascota.objects.filter(pk=self.pet.pk).exists())
        self.assertTrue(Cliente.objects.filter(pk=self.client_a.pk).exists())

    def test_deleting_pet_with_clinical_history_is_rejected(self):
        appointment = self.appointment()
        response = self.client.delete(f"/inicio/api/eliminar-registro/{self.pet.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Cita.objects.filter(pk=appointment.pk).exists())
        self.assertTrue(Mascota.objects.filter(pk=self.pet.pk).exists())

    def test_booking_saves_owner_and_prevents_conflicting_slots(self):
        response = self.client.post("/inicio/api/registrar/cita/", self.appointment_payload())
        self.assertEqual(response.status_code, 200)
        appointment = Cita.objects.get(pk=response.json()["cita_id"])
        self.assertEqual(appointment.cliente_id_id, self.client_a.pk)
        response = self.client.post("/inicio/api/registrar/cita/", self.appointment_payload(mascota=self.pet_b.pk))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Cita.objects.count(), 1)

    def test_booking_rejects_invalid_dates_states_and_ids(self):
        for invalid in (
            {"fecha": "not-date"}, {"fecha": (self.today - timedelta(days=1)).isoformat()},
            {"hora": "88:99"}, {"estado": "inventado"}, {"mascota": "invalid"},
            {"mascota": "9" * 80},
        ):
            with self.subTest(data=invalid):
                self.assertEqual(self.client.post("/inicio/api/registrar/cita/",
                    self.appointment_payload(**invalid)).status_code, 400)
        self.assertEqual(Cita.objects.count(), 0)

    def test_cancelled_slot_can_be_reused_but_not_reactivated_over_another(self):
        old = self.appointment(fecha=self.tomorrow, estado="Cancelada")
        self.assertEqual(self.client.post("/inicio/api/registrar/cita/",
            self.appointment_payload(mascota=self.pet_b.pk)).status_code, 200)
        response = self.client.post(f"/inicio/api/citas/{old.pk}/estado/", {"estado": "Confirmada"})
        self.assertEqual(response.status_code, 409)
        old.refresh_from_db()
        self.assertEqual(old.estado, "Cancelada")

    def test_cannot_mark_future_appointment_attended(self):
        appointment = self.appointment(fecha=self.tomorrow)
        response = self.client.post(f"/inicio/api/citas/{appointment.pk}/estado/", {"estado": "Atendida"})
        self.assertEqual(response.status_code, 400)

    def test_cannot_cancel_appointment_with_treatment(self):
        appointment = self.appointment()
        Tratamiento.objects.create(cita_id=appointment, descripcion="Control", medicamento="Ejemplo",
            dosis="Según fórmula", duracion="1 día", fecha_inicio=self.today)
        response = self.client.post(f"/inicio/api/citas/{appointment.pk}/estado/", {"estado": "Cancelada"})
        self.assertEqual(response.status_code, 409)

    def test_vaccine_dates_and_duplicate_applications(self):
        data = dict(mascota_id=self.pet.pk, nombre_vacuna="Ejemplo", fecha_aplicacion=self.today.isoformat(),
                    fecha_vencimiento=(self.today + timedelta(days=30)).isoformat(), lote="TEST")
        self.assertEqual(self.client.post("/inicio/api/registrar-vacuna/",
            {**data, "fecha_vencimiento": (self.today - timedelta(days=1)).isoformat()}).status_code, 400)
        self.assertEqual(self.client.post("/inicio/api/registrar-vacuna/", data).status_code, 200)
        self.assertEqual(self.client.post("/inicio/api/registrar-vacuna/", data).status_code, 409)
        self.assertEqual(Historial_de_Vacunas.objects.count(), 1)

    def test_treatment_rejects_cancelled_appointment(self):
        appointment = self.appointment(estado="Cancelada")
        data = dict(cita_id=appointment.pk, descripcion="Control", medicamento="Ejemplo",
                    dosis="Según fórmula", duracion="1 día", fecha_inicio=self.today.isoformat())
        self.assertEqual(self.client.post("/inicio/api/registrar-tratamiento/", data).status_code, 409)
        self.assertFalse(Tratamiento.objects.exists())

    def test_invoice_invalid_amounts_return_validation_instead_of_server_errors(self):
        appointment = self.appointment()
        for amount in ("NaN", "Infinity", "-1", "0", "1.001", "invalid"):
            with self.subTest(amount=amount):
                response = self.client.post("/inicio/api/registrar-factura/",
                    self.invoice_payload(appointment, monto_total=amount))
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Factura.objects.exists())

    def test_invoice_rejects_other_customer_or_impersonated_administrator(self):
        appointment = self.appointment()
        for invalid in ({"cliente_id": self.client_b.pk}, {"administrador_id": self.other_operator.pk}):
            response = self.client.post("/inicio/api/registrar-factura/",
                self.invoice_payload(appointment, **invalid))
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Factura.objects.exists())

    def test_invoice_creation_records_actor_and_prevents_duplicate(self):
        appointment = self.appointment()
        response = self.client.post("/inicio/api/registrar-factura/", self.invoice_payload(appointment))
        self.assertEqual(response.status_code, 200)
        invoice = Factura.objects.get()
        self.assertEqual(invoice.administrador_id, self.operator)
        self.assertEqual(invoice.monto_total, Decimal("100.50"))
        self.assertEqual(self.client.post("/inicio/api/registrar-factura/",
            self.invoice_payload(appointment)).status_code, 409)

    def test_appointment_billing_owner_is_preserved_after_pet_transfer(self):
        appointment = self.appointment()
        self.pet.cliente_id = self.client_b
        self.pet.save(update_fields=["cliente_id"])
        response = self.client.get("/inicio/api/datos-factura/")
        self.assertEqual(response.json()["citas"][0]["cliente_id"], self.client_a.pk)
        response = self.client.post("/inicio/api/registrar-factura/", self.invoice_payload(appointment))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Factura.objects.get().cliente_id_id, self.client_a.pk)

    def test_nonstaff_cannot_modify_invoices(self):
        self.operator.is_staff = False
        self.operator.save(update_fields=["is_staff"])
        response = self.client.post("/inicio/api/registrar-factura/", self.invoice_payload(self.appointment()))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Factura.objects.exists())

    def test_cancelled_invoice_cannot_replace_another_active_invoice(self):
        appointment = self.appointment()
        cancelled = Factura.objects.create(cita_id=appointment, cliente_id=self.client_a,
            administrador_id=self.operator, monto_total="10", estado_pago="Cancelada", fecha_emision=self.today)
        self.client.post("/inicio/api/registrar-factura/", self.invoice_payload(appointment))
        response = self.client.post("/inicio/api/actualizar-estado-factura/",
            {"factura_id": cancelled.pk, "estado_pago": "Pagada"})
        self.assertEqual(response.status_code, 409)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.estado_pago, "Cancelada")

    def test_invoice_cannot_be_reactivated_for_cancelled_appointment(self):
        appointment = self.appointment(estado="Cancelada")
        invoice = Factura.objects.create(cita_id=appointment, cliente_id=self.client_a,
            administrador_id=self.operator, fecha_emision=self.today,
            monto_total=Decimal("100"), estado_pago="Cancelada")
        response = self.client.post("/inicio/api/actualizar-estado-factura/",
            {"factura_id": invoice.pk, "estado_pago": "Pagada"})
        self.assertEqual(response.status_code, 409)
        invoice.refresh_from_db()
        self.assertEqual(invoice.estado_pago, "Cancelada")

    def test_dashboard_uses_active_clients_and_latest_vaccine_application(self):
        self.client_b.estado = "Inactivo"
        self.client_b.save(update_fields=["estado"])
        Historial_de_Vacunas.objects.create(mascota_id=self.pet, nombre_vacuna="Ejemplo",
            fecha_aplic=self.today - timedelta(days=60), fecha_venc=self.today - timedelta(days=30), lote="OLD")
        Historial_de_Vacunas.objects.create(mascota_id=self.pet, nombre_vacuna="Ejemplo",
            fecha_aplic=self.today, fecha_venc=self.today + timedelta(days=365), lote="NEW")
        Historial_de_Vacunas.objects.create(mascota_id=self.pet_b, nombre_vacuna="Otra",
            fecha_aplic=self.today, fecha_venc=self.today + timedelta(days=10), lote="DUE")
        response = self.client.get("/inicio/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_clientes_activos"], 1)
        self.assertEqual(response.json()["total_vacunas_pendientes"], 1)

    def test_invalid_json_and_oversized_id_fail_safely(self):
        response = self.client.post("/inicio/api/registrar/cliente/", "{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/inicio/api/editar-cliente/",
            {**self.customer_payload(), "cliente_id": "9" * 5000})
        self.assertEqual(response.status_code, 400)

