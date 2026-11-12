from django import forms


class RegistroAdopcionForm(forms.Form):
    mascota_id = forms.IntegerField(min_value=1)
    responsable_id = forms.IntegerField(min_value=1)
    motivo = forms.CharField(max_length=1000)
    observaciones = forms.CharField(max_length=2000, required=False)


class ConfirmarAdopcionForm(forms.Form):
    cliente_adoptante_id = forms.IntegerField(min_value=1)
    evaluacion_id = forms.IntegerField(min_value=1)
    observaciones = forms.CharField(max_length=2000, required=False)


class EvaluacionForm(forms.Form):
    cliente_adoptante_id = forms.IntegerField(min_value=1)
    horas_disponibles = forms.DecimalField(min_value=0, max_value=24, max_digits=4, decimal_places=2)
    ingresos_mensuales = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
    gastos_mensuales = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
    presupuesto_mascota = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
    vivienda_apta = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
    permiso_vivienda = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
    acceso_veterinario = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
    experiencia = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
    apoyo_ausencias = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
    compromiso_cuidado = forms.TypedChoiceField(choices=(("si", "Sí"), ("no", "No")), coerce=lambda value: value == "si")
