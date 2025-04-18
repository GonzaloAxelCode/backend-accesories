# Generated by Django 5.1.2 on 2025-03-08 02:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0003_inventario_descripcion_inventario_proveedor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventario",
            name="costo_compra",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="inventario",
            name="costo_docena",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="inventario",
            name="costo_venta",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]
