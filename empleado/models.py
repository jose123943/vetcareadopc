from django.db import models

# Create your models here.
class Empleado(models.Model):

    id_empleado = models.BigAutoField (primary_key=True, db_column='id_empleado')
    nombre = models.CharField (max_length=50, db_column='nombre')
    apellido = models.CharField (max_length=50, db_column='apellido')
    telefono = models.CharField(max_length=20, blank=True, db_column='telefono')
    cargo = models.CharField(max_length=100, blank=True, default='', db_column='cargo')

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()

    class Meta:
        db_table = 'empleado'  
