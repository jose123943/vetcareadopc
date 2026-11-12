from django.contrib import admin

from .models import Empleado


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('id_empleado', 'nombre', 'apellido', 'cargo', 'telefono')
    list_filter = ('cargo',)
    search_fields = ('nombre', 'apellido', 'cargo')
