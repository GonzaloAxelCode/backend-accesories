# Generated by Django 4.2 on 2025-04-08 02:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='caja',
            name='fecha_cancelacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='caja',
            name='fecha_reinicio',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='operacioncaja',
            name='tipo',
            field=models.CharField(choices=[('ingreso', 'Ingreso'), ('gasto', 'Gasto'), ('prestamo', 'Préstamo'), ('venta', 'Venta')], max_length=20),
        ),
    ]
