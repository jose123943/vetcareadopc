from django.contrib import admin

from .models import Adopcion, EvaluacionAdopcion


@admin.register(Adopcion)
class AdopcionAdmin(admin.ModelAdmin):
    list_display = ("id", "mascota", "cliente_origen", "cliente_adoptante", "responsable", "estado", "fecha_registro")
    list_filter = ("estado", "responsable")
    search_fields = ("mascota__nombre", "cliente_origen__nombre", "cliente_adoptante__nombre")
    list_select_related = ("mascota", "cliente_origen", "cliente_adoptante", "responsable")
    readonly_fields = tuple(field.name for field in Adopcion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EvaluacionAdopcion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("id", "adopcion", "cliente", "puntaje", "aprobada", "fecha")
    list_filter = ("aprobada",)
    readonly_fields = tuple(field.name for field in EvaluacionAdopcion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
