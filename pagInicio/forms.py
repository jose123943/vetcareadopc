"""Validación de los datos enviados por los formularios del dashboard."""

from decimal import Decimal

from django import forms
from django.utils import timezone

from cita.models import Cita
from cliente.models import Cliente


PAYMENT_STATES = [(value, value) for value in ("Pendiente", "Pagada", "Cancelada")]


class RecordIdField(forms.IntegerField):
    def __init__(self, **kwargs):
        super().__init__(min_value=1, max_value=9223372036854775807, **kwargs)


class ClienteForm(forms.Form):
    nombre = forms.CharField(max_length=50)
    apellido = forms.CharField(max_length=50)
    direccion = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=100)
    telefono = forms.RegexField(r"^[0-9+(). -]{7,20}$", max_length=20,
                                error_messages={"invalid": "Ingresa un teléfono válido."})
    estado = forms.ChoiceField(choices=Cliente.ESTADOS, required=False)


class MascotaForm(forms.Form):
    nombreMascota = forms.CharField(max_length=50)
    especie = forms.CharField(max_length=50)
    raza = forms.CharField(max_length=50)
    edad = forms.IntegerField(min_value=0, max_value=50)
    peso = forms.DecimalField(min_value=Decimal("0"), max_value=Decimal("500"),
                              max_digits=5, decimal_places=2)


class CitaForm(forms.Form):
    fecha = forms.DateField(input_formats=["%Y-%m-%d"])
    hora = forms.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    motivo = forms.CharField(max_length=200)
    estado = forms.ChoiceField(choices=Cita.ESTADOS, required=False)
    mascota = RecordIdField()
    veterinario = RecordIdField()

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("La fecha de la cita no puede estar en el pasado.")
        return fecha


class VacunaForm(forms.Form):
    mascota_id = RecordIdField()
    nombre_vacuna = forms.CharField(max_length=100)
    fecha_aplicacion = forms.DateField(input_formats=["%Y-%m-%d"])
    fecha_vencimiento = forms.DateField(input_formats=["%Y-%m-%d"])
    lote = forms.CharField(max_length=50)

    def clean(self):
        cleaned = super().clean()
        applied = cleaned.get("fecha_aplicacion")
        expires = cleaned.get("fecha_vencimiento")
        if applied and applied > timezone.localdate():
            self.add_error("fecha_aplicacion", "No puedes registrar una aplicación futura.")
        if applied and expires and expires < applied:
            self.add_error("fecha_vencimiento", "El vencimiento no puede ser anterior a la aplicación.")
        return cleaned


class TratamientoForm(forms.Form):
    cita_id = RecordIdField()
    descripcion = forms.CharField(max_length=200)
    medicamento = forms.CharField(max_length=100)
    dosis = forms.CharField(max_length=50)
    duracion = forms.CharField(max_length=50)
    fecha_inicio = forms.DateField(input_formats=["%Y-%m-%d"])


class FacturaForm(forms.Form):
    fecha_emision = forms.DateField(input_formats=["%Y-%m-%d"])
    monto_total = forms.DecimalField(min_value=Decimal("0.01"), max_digits=10, decimal_places=2)
    estado_pago = forms.ChoiceField(choices=PAYMENT_STATES)
    cita_id = RecordIdField()
    cliente_id = RecordIdField()
    administrador_id = RecordIdField(required=False)

    def clean_fecha_emision(self):
        fecha = self.cleaned_data["fecha_emision"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de emisión no puede ser futura.")
        return fecha


def validated(form_class, data):
    form = form_class(data)
    if not form.is_valid():
        from django.core.exceptions import ValidationError
        raise ValidationError({name: list(errors) for name, errors in form.errors.items()})
    return form.cleaned_data
