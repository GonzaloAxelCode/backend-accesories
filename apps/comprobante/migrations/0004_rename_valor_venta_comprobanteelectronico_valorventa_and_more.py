# Generated by Django 4.2 on 2025-03-15 00:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comprobante', '0003_comprobanteelectronico_cdr_url_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comprobanteelectronico',
            old_name='valor_venta',
            new_name='valorVenta',
        ),
        migrations.RemoveField(
            model_name='comprobanteelectronico',
            name='direccion_cliente',
        ),
        migrations.RemoveField(
            model_name='comprobanteelectronico',
            name='email_cliente',
        ),
        migrations.RemoveField(
            model_name='comprobanteelectronico',
            name='numero',
        ),
        migrations.RemoveField(
            model_name='comprobanteelectronico',
            name='telefono_cliente',
        ),
        migrations.AddField(
            model_name='comprobanteelectronico',
            name='correlativo',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='comprobanteelectronico',
            name='items',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='comprobanteelectronico',
            name='moneda',
            field=models.CharField(max_length=10, null=True),
        ),
    ]
