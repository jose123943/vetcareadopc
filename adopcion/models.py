from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Adopcion(models.Model):
    class Estado(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        ADOPTADA = "adoptada", "Adoptada"
        CANCELADA = "cancelada", "Cancelada"

    mascota = models.ForeignKey("mascota.Mascota", on_delete=models.PROTECT, related_name="adopciones")
    cliente_origen = models.ForeignKey("cliente.Cliente", on_delete=models.PROTECT, related_name="adopciones_entregadas")
    cliente_adoptante = models.ForeignKey("cliente.Cliente", on_delete=models.PROTECT, related_name="adopciones_recibidas", null=True, blank=True)
    responsable = models.ForeignKey("empleado.Empleado", on_delete=models.PROTECT, related_name="adopciones_a_cargo")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.DISPONIBLE, db_index=True)
    # MySQL admite varios NULL en una clave única; solo una fila puede estar activa.
    activa = models.BooleanField(default=True, null=True, blank=True, editable=False)
    evaluacion_aprobada = models.ForeignKey("EvaluacionAdopcion", on_delete=models.PROTECT, null=True, blank=True, related_name="adopciones_confirmadas")
    motivo = models.CharField(max_length=1000)
    observaciones = models.TextField(max_length=2000, blank=True)
    observaciones_adopcion = models.TextField(max_length=2000, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_adopcion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="adopciones_creadas")
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="adopciones_cerradas")

    class Meta:
        db_table = "adopcion"
        verbose_name = "adopción"
        verbose_name_plural = "adopciones"
        ordering = ("-fecha_registro", "-pk")
        constraints = [
            models.UniqueConstraint(fields=("mascota", "activa"), name="adopcion_una_activa_por_mascota"),
            models.CheckConstraint(
                condition=(Q(estado="disponible", activa=True, activa__isnull=False, fecha_cierre__isnull=True)
                           | Q(estado__in=("adoptada", "cancelada"), activa__isnull=True, fecha_cierre__isnull=False)),
                name="adopcion_estado_activa_coherente",
            ),
            models.CheckConstraint(
                condition=(Q(estado="adoptada", cliente_adoptante__isnull=False, fecha_adopcion__isnull=False, evaluacion_aprobada__isnull=False)
                           | Q(estado__in=("disponible", "cancelada"), cliente_adoptante__isnull=True, fecha_adopcion__isnull=True, evaluacion_aprobada__isnull=True)),
                name="adopcion_destino_coherente",
            ),
            models.CheckConstraint(
                condition=Q(cliente_adoptante__isnull=True) | ~Q(cliente_origen=F("cliente_adoptante")),
                name="adopcion_clientes_distintos",
            ),
        ]

    def __str__(self):
        return f"{self.mascota.nombre} — {self.get_estado_display()}"


class EvaluacionAdopcion(models.Model):
    adopcion = models.ForeignKey(Adopcion, on_delete=models.PROTECT, related_name="evaluaciones")
    cliente = models.ForeignKey("cliente.Cliente", on_delete=models.PROTECT, related_name="evaluaciones_adopcion")
    respuestas = models.JSONField()
    desglose = models.JSONField()
    puntaje = models.PositiveSmallIntegerField()
    aprobada = models.BooleanField()
    version = models.CharField(max_length=30, default="vetcare-v1")
    fecha = models.DateTimeField(auto_now_add=True)
    evaluado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "evaluacion_adopcion"
        verbose_name = "evaluación de adopción"
        verbose_name_plural = "evaluaciones de adopción"
        ordering = ("-fecha", "-pk")
        constraints = [
            models.CheckConstraint(condition=Q(puntaje__lte=100), name="evaluacion_rango_0_100"),
            models.CheckConstraint(
                condition=Q(puntaje__gt=70, aprobada=True) | Q(puntaje__lte=70, aprobada=False),
                name="evaluacion_aprobacion_mayor_70",
            ),
        ]

    def __str__(self):
        return f"Evaluación {self.pk}: {self.puntaje}%"
