from django.db import migrations, models
import django.db.models.deletion


def preserve_appointment_clients(apps, schema_editor):
    Cita = apps.get_model('cita', 'Cita')
    for appointment in Cita.objects.using(schema_editor.connection.alias).select_related('mascota_id').iterator(chunk_size=500):
        appointment.cliente_id_id = appointment.mascota_id.cliente_id_id
        appointment.save(using=schema_editor.connection.alias, update_fields=['cliente_id'])


class Migration(migrations.Migration):
    dependencies = [
        ('cita', '0001_initial'),
        ('cliente', '0002_alter_cliente_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='cita', name='cliente_id',
            field=models.ForeignKey(
                blank=True, db_column='cliente_id',
                help_text='Cliente responsable al registrar la cita; se conserva tras una adopción.',
                null=True, on_delete=django.db.models.deletion.PROTECT, to='cliente.cliente',
            ),
        ),
        migrations.RunPython(preserve_appointment_clients, migrations.RunPython.noop),
    ]
