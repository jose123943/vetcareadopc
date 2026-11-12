from django.contrib import admin

from .models import Veterinario


@admin.register(Veterinario)
class VeterinarioAdmin(admin.ModelAdmin):
    list_display = ('id_veterinario', 'especialidad')
    list_filter = ('especialidad',)
    search_fields = ('id_veterinario__nombre', 'id_veterinario__apellido', 'especialidad')
    autocomplete_fields = ('id_veterinario',)
