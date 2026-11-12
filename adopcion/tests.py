from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from cita.models import Cita
from cliente.models import Cliente
from empleado.models import Empleado
from empl_veterinario.models import Veterinario
from factura.models import Factura
from historial_de_vacunas.models import Historial_de_Vacunas
from mascota.models import Mascota
from tratamiento.models import Tratamiento

from . import services
from .evaluation import calcular
from .forms import EvaluacionForm
from .models import Adopcion, EvaluacionAdopcion


def answers(**changes):
    data = {
        "horas_disponibles": Decimal("3"),
        "ingresos_mensuales": Decimal("3000.00"),
        "gastos_mensuales": Decimal("1000.00"),
        "presupuesto_mascota": Decimal("500.00"),
        "vivienda_apta": True,
        "permiso_vivienda": True,
        "acceso_veterinario": True,
        "experiencia": True,
        "apoyo_ausencias": True,
        "compromiso_cuidado": True,
    }
    data.update(changes)
    return data


def form_answers(client_id, **changes):
    data = {
        key: ("si" if value else "no") if isinstance(value, bool) else str(value)
        for key, value in answers().items()
    }
    data["cliente_adoptante_id"] = client_id
    data.update(changes)
    return data


class EvaluationRuleTests(SimpleTestCase):
    def test_score_is_bounded_and_all_criteria_add_up_to_100(self):
        score, approved, breakdown = calcular(answers())
        self.assertEqual(score, 100)
        self.assertTrue(approved)
        self.assertEqual(sum(item["maximo"] for item in breakdown), 100)
        self.assertEqual(sum(item["puntos"] for item in breakdown), score)

    def test_threshold_is_strictly_greater_than_70(self):
        score, approved, _ = calcular(answers(horas_disponibles=Decimal("0"), experiencia=False))
        self.assertEqual(score, 70)
        self.assertFalse(approved)
        score, approved, _ = calcular(answers(horas_disponibles=Decimal("0")))
        self.assertEqual(score, 75)
        self.assertTrue(approved)

    def test_zero_or_unsustainable_budget_earns_no_financial_points(self):
        cases = (
            {"ingresos_mensuales": Decimal("0"), "gastos_mensuales": Decimal("0")},
            {"presupuesto_mascota": Decimal("0")},
            {"ingresos_mensuales": Decimal("100"), "gastos_mensuales": Decimal("90"), "presupuesto_mascota": Decimal("20")},
            {"gastos_mensuales": Decimal("5000")},
        )
        for case in cases:
            with self.subTest(case=case):
                _, _, breakdown = calcular(answers(**case))
                self.assertEqual(breakdown[1]["puntos"], 0)

    def test_capacity_uses_disposable_income_not_gross_income(self):
        _, _, breakdown = calcular(answers(
            ingresos_mensuales=Decimal("100"), gastos_mensuales=Decimal("80"),
            presupuesto_mascota=Decimal("20"),
        ))
        self.assertEqual(breakdown[1]["puntos"], 20)

    def test_form_rejects_nonfinite_negative_or_out_of_range_values(self):
        for field in ("horas_disponibles", "ingresos_mensuales", "gastos_mensuales", "presupuesto_mascota"):
            for value in ("NaN", "Infinity", "-Infinity", "-1"):
                with self.subTest(field=field, value=value):
                    form = EvaluacionForm(form_answers(1, **{field: value}))
                    self.assertFalse(form.is_valid())
                    self.assertIn(field, form.errors)
        self.assertFalse(EvaluacionForm(form_answers(1, horas_disponibles="25")).is_valid())

    def test_form_rejects_unknown_choices_and_does_not_accept_client_score(self):
        form = EvaluacionForm(form_answers(1, vivienda_apta="tal vez"))
        self.assertFalse(form.is_valid())
        form = EvaluacionForm(form_answers(1, puntaje="100", aprobada="true"))
        self.assertTrue(form.is_valid())
        self.assertNotIn("puntaje", form.cleaned_data)
        self.assertNotIn("aprobada", form.cleaned_data)


class AdoptionDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="adoption-auditor", password="test-only")
        cls.owner = cls.create_client("Origen")
        cls.adopter = cls.create_client("Adoptante")
        cls.other = cls.create_client("Otro")
        cls.manager = Empleado.objects.create(
            nombre="Responsable", apellido="QA", telefono="", cargo="Encargado de adopciones"
        )
        cls.vet_employee = Empleado.objects.create(
            nombre="Veterinario", apellido="QA", telefono="", cargo="Veterinario"
        )
        cls.vet = Veterinario.objects.create(id_veterinario=cls.vet_employee, especialidad="Medicina interna")
        cls.pet = cls.create_pet("Luna", cls.owner)

    @staticmethod
    def create_client(name):
        return Cliente.objects.create(
            nombre=name, apellido="QA", telefono="0000000000", direccion="Dirección de prueba",
            email=f"{name.lower()}@example.invalid", estado="Activo",
        )

    @staticmethod
    def create_pet(name, owner):
        return Mascota.objects.create(
            nombre=name, especie="Perro", raza="Mestizo", edad=3, peso=Decimal("12.50"), cliente_id=owner
        )

    def register(self, pet=None):
        return services.registrar(
            mascota_id=(pet or self.pet).pk, responsable_id=self.manager.pk,
            motivo="Cambio de circunstancias familiares", observaciones="Caso de prueba", usuario=self.user,
        )

    def evaluate(self, adoption, client=None, **changes):
        return services.evaluar(
            adopcion_id=adoption.pk, cliente_adoptante_id=(client or self.adopter).pk,
            usuario=self.user, **answers(**changes),
        )

    def adopt(self, adoption, evaluation, client=None):
        return services.adoptar(
            adopcion_id=adoption.pk, cliente_adoptante_id=(client or self.adopter).pk,
            evaluacion_id=evaluation.pk, observaciones="Entrega documentada", usuario=self.user,
        )


class AdoptionLifecycleTests(AdoptionDataMixin, TestCase):
    def test_publication_keeps_current_owner_and_prevents_a_second_available_offer(self):
        adoption = self.register()
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.cliente_id_id, self.owner.pk)
        self.assertEqual(adoption.cliente_origen_id, self.owner.pk)
        self.assertEqual(adoption.responsable_id, self.manager.pk)
        with self.assertRaises(services.AdoptionConflict):
            self.register()
        self.assertEqual(Adopcion.objects.count(), 1)

    def test_inactive_owner_and_wrong_responsible_cannot_publish(self):
        self.owner.estado = "Inactivo"
        self.owner.save(update_fields=["estado"])
        with self.assertRaises(ValidationError):
            self.register()
        self.owner.estado = "Activo"
        self.owner.save(update_fields=["estado"])
        with self.assertRaises(Empleado.DoesNotExist):
            services.registrar(
                mascota_id=self.pet.pk, responsable_id=self.vet_employee.pk,
                motivo="Prueba", observaciones="", usuario=self.user,
            )
        self.assertFalse(Adopcion.objects.exists())

    def test_cancel_allows_republication_without_deleting_history(self):
        first = self.register()
        services.cancelar(adopcion_id=first.pk, usuario=self.user)
        second = self.register()
        services.cancelar(adopcion_id=second.pk, usuario=self.user)
        third = self.register()
        self.assertEqual(Adopcion.objects.count(), 3)
        self.assertEqual(Adopcion.objects.filter(activa__isnull=True).count(), 2)
        self.assertEqual(Adopcion.objects.get(activa=True).pk, third.pk)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.cliente_id_id, self.owner.pk)
        with self.assertRaises(services.AdoptionConflict):
            services.cancelar(adopcion_id=first.pk, usuario=self.user)

    def test_confirm_transfers_ownership_and_preserves_medical_and_billing_history(self):
        today = timezone.localdate()
        appointment = Cita.objects.create(
            mascota_id=self.pet, veterinario_id=self.vet, fecha=today, hora=time(10),
            motivo="Consulta anterior", estado="Atendida",
        )
        vaccine = Historial_de_Vacunas.objects.create(
            mascota_id=self.pet, nombre_vacuna="Vacuna de prueba", fecha_aplic=today,
            fecha_venc=today + timedelta(days=365), lote="QA-001",
        )
        treatment = Tratamiento.objects.create(
            cita_id=appointment, descripcion="Historial de prueba", medicamento="Prueba",
            dosis="Según registro", duracion="Registro", fecha_inicio=today,
        )
        invoice = Factura.objects.create(
            cliente_id=self.owner, cita_id=appointment, administrador_id=self.user,
            fecha_emision=today, monto_total=Decimal("100.00"), estado_pago="Pagada",
        )
        adoption = self.register()
        evaluation = self.evaluate(adoption)
        result = self.adopt(adoption, evaluation)
        self.pet.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(self.pet.cliente_id_id, self.adopter.pk)
        self.assertEqual(result.estado, "adoptada")
        self.assertIsNone(result.activa)
        self.assertEqual(result.cliente_origen_id, self.owner.pk)
        self.assertEqual(result.evaluacion_aprobada_id, evaluation.pk)
        self.assertEqual(invoice.cliente_id_id, self.owner.pk)
        self.assertTrue(Cita.objects.filter(pk=appointment.pk).exists())
        self.assertTrue(Historial_de_Vacunas.objects.filter(pk=vaccine.pk, mascota_id=self.pet).exists())
        self.assertTrue(Tratamiento.objects.filter(pk=treatment.pk).exists())
        self.assertIsNotNone(result.fecha_adopcion)
        with self.assertRaises(services.AdoptionConflict):
            self.adopt(adoption, evaluation)

    def test_owner_cannot_adopt_and_inactive_client_cannot_be_evaluated(self):
        adoption = self.register()
        with self.assertRaises(ValidationError):
            self.evaluate(adoption, client=self.owner)
        self.adopter.estado = "Inactivo"
        self.adopter.save(update_fields=["estado"])
        with self.assertRaises(Cliente.DoesNotExist):
            self.evaluate(adoption)

    def test_inactive_adopter_is_rejected_even_after_an_approved_evaluation(self):
        adoption = self.register()
        evaluation = self.evaluate(adoption)
        self.adopter.estado = "Inactivo"
        self.adopter.save(update_fields=["estado"])
        with self.assertRaises(ValidationError):
            self.adopt(adoption, evaluation)

    def test_failed_adoption_rolls_back_the_owner_change(self):
        adoption = self.register()
        evaluation = self.evaluate(adoption)
        with patch.object(Adopcion, "save", side_effect=RuntimeError("simulated persistence failure")):
            with self.assertRaises(RuntimeError):
                self.adopt(adoption, evaluation)
        self.pet.refresh_from_db()
        adoption.refresh_from_db()
        self.assertEqual(self.pet.cliente_id_id, self.owner.pk)
        self.assertEqual(adoption.estado, "disponible")
        self.assertIsNone(adoption.cliente_adoptante_id)

    def test_ownership_change_after_publication_blocks_confirmation(self):
        adoption = self.register()
        evaluation = self.evaluate(adoption)
        Mascota.objects.filter(pk=self.pet.pk).update(cliente_id=self.other)
        with self.assertRaises(services.AdoptionConflict):
            self.adopt(adoption, evaluation)

    def test_evaluation_is_bound_to_adoption_and_client(self):
        adoption = self.register()
        evaluation = self.evaluate(adoption)
        with self.assertRaises(EvaluacionAdopcion.DoesNotExist):
            self.adopt(adoption, evaluation, client=self.other)
        another = self.register(self.create_pet("Nala", self.owner))
        with self.assertRaises(EvaluacionAdopcion.DoesNotExist):
            self.adopt(another, evaluation)

    def test_older_approval_cannot_override_a_newer_rejection(self):
        adoption = self.register()
        approved = self.evaluate(adoption)
        rejected = self.evaluate(adoption, horas_disponibles=Decimal("0"), experiencia=False)
        self.assertEqual(rejected.puntaje, 70)
        with self.assertRaises(services.AdoptionConflict):
            self.adopt(adoption, approved)
        with self.assertRaises(ValidationError):
            self.adopt(adoption, rejected)
        adoption.refresh_from_db()
        self.assertEqual(adoption.estado, "disponible")

    def test_evaluation_snapshot_preserves_decimal_inputs_and_breakdown(self):
        evaluation = self.evaluate(self.register(), ingresos_mensuales=Decimal("3000.55"))
        self.assertEqual(evaluation.respuestas["ingresos_mensuales"], "3000.55")
        self.assertIs(evaluation.respuestas["vivienda_apta"], True)
        self.assertEqual(sum(item["puntos"] for item in evaluation.desglose), evaluation.puntaje)

    def test_history_protects_pet_customers_and_responsible_from_deletion(self):
        adoption = self.register()
        self.evaluate(adoption)
        for record in (self.pet, self.owner, self.adopter, self.manager, adoption):
            with self.subTest(model=type(record).__name__):
                with self.assertRaises(ProtectedError):
                    record.delete()


class AdoptionConstraintTests(AdoptionDataMixin, TestCase):
    def test_database_rejects_duplicate_active_publication_without_service(self):
        self.register()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Adopcion.objects.create(
                mascota=self.pet, cliente_origen=self.owner, responsable=self.manager,
                motivo="Duplicada", creado_por=self.user,
            )

    def test_database_rejects_inconsistent_closed_state(self):
        adoption = self.register()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Adopcion.objects.filter(pk=adoption.pk).update(estado="cancelada")

    def test_database_rejects_inconsistent_adoption_destination(self):
        adoption = self.register()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Adopcion.objects.filter(pk=adoption.pk).update(
                estado="adoptada", activa=None, fecha_cierre=timezone.now()
            )

    def test_database_enforces_evaluation_range_and_strict_threshold(self):
        adoption = self.register()
        for score, approved in ((70, True), (75, False), (101, True), (-1, False)):
            with self.subTest(score=score, approved=approved):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    EvaluacionAdopcion.objects.create(
                        adopcion=adoption, cliente=self.adopter, respuestas={"test": True},
                        desglose=[{"puntos": score}], puntaje=score, aprobada=approved,
                        evaluado_por=self.user,
                    )


class AdoptionApiTests(AdoptionDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_anonymous_cannot_read_adoptions_or_economic_evaluations(self):
        adoption = self.register()
        self.evaluate(adoption)
        anonymous = Client()
        for path in ("/adopciones/api/", "/adopciones/api/datos/", f"/adopciones/api/{adoption.pk}/evaluaciones/"):
            with self.subTest(path=path):
                response = anonymous.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertNotContains(response, "ingresos_mensuales", status_code=401)

    def test_mutations_require_post_and_csrf(self):
        self.assertEqual(self.client.get("/adopciones/api/registrar/").status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post("/adopciones/api/registrar/", {
            "mascota_id": self.pet.pk, "responsable_id": self.manager.pk, "motivo": "Prueba",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Adopcion.objects.exists())

    def test_available_data_excludes_pets_already_published(self):
        self.register()
        response = self.client.get("/adopciones/api/datos/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.pet.pk, [row["id"] for row in response.json()["mascotas"]])
        self.assertEqual([row["id"] for row in response.json()["responsables"]], [self.manager.pk])

    def test_publication_evaluation_and_confirmation_http_lifecycle(self):
        response = self.client.post("/adopciones/api/registrar/", {
            "mascota_id": self.pet.pk, "responsable_id": self.manager.pk, "motivo": "Prueba de flujo",
        })
        self.assertEqual(response.status_code, 201)
        adoption_id = response.json()["id"]
        endpoint = f"/adopciones/api/{adoption_id}"
        response = self.client.post(f"{endpoint}/evaluar/", form_answers(self.adopter.pk))
        self.assertEqual(response.status_code, 201)
        evaluation = response.json()["evaluacion"]
        self.assertEqual(evaluation["puntaje"], 100)
        self.assertTrue(evaluation["aprobada"])
        response = self.client.post(f"{endpoint}/adoptar/", {
            "cliente_adoptante_id": self.adopter.pk, "evaluacion_id": evaluation["id"],
        })
        self.assertEqual(response.status_code, 200)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.cliente_id_id, self.adopter.pk)

    def test_client_supplied_score_cannot_override_server_evaluation(self):
        adoption = self.register()
        response = self.client.post(f"/adopciones/api/{adoption.pk}/evaluar/", form_answers(
            self.adopter.pk, horas_disponibles="0", experiencia="no", puntaje="100", aprobada="true",
        ))
        self.assertEqual(response.status_code, 201)
        evaluation = response.json()["evaluacion"]
        self.assertEqual(evaluation["puntaje"], 70)
        self.assertFalse(evaluation["aprobada"])
        response = self.client.post(f"/adopciones/api/{adoption.pk}/adoptar/", {
            "cliente_adoptante_id": self.adopter.pk, "evaluacion_id": evaluation["id"],
        })
        self.assertEqual(response.status_code, 400)

    def test_invalid_evaluation_has_validation_errors_and_does_not_save(self):
        adoption = self.register()
        response = self.client.post(f"/adopciones/api/{adoption.pk}/evaluar/", form_answers(
            self.adopter.pk, ingresos_mensuales="NaN",
        ))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EvaluacionAdopcion.objects.exists())

    def test_filter_rejects_unknown_state_and_missing_records_return_404(self):
        self.assertEqual(self.client.get("/adopciones/api/?estado=invalid").status_code, 400)
        self.assertEqual(self.client.get("/adopciones/api/999999/evaluaciones/").status_code, 404)
