# Renombra api_client_id/api_client_secret a client_id/client_secret
# (keys de SUNAT para guías) preservando los valores ya guardados.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tienda", "0020_tienda_api_client_id_tienda_api_client_secret"),
    ]

    operations = [
        migrations.RenameField(
            model_name="tienda",
            old_name="api_client_id",
            new_name="client_id",
        ),
        migrations.RenameField(
            model_name="tienda",
            old_name="api_client_secret",
            new_name="client_secret",
        ),
        migrations.AlterField(
            model_name="tienda",
            name="client_id",
            field=models.CharField(blank=True, default="", max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="tienda",
            name="client_secret",
            field=models.CharField(blank=True, default="", max_length=255, null=True),
        ),
    ]
