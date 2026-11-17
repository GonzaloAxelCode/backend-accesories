# Migración manual: xml_url pasa a ser xml_constancia (conserva el dato),
# se agregan xml_comprobante (XML real del proveedor) y pdf_url.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compras", "0010_rename_cdr_codigo_comprobantecompra_estado_codigo_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="comprobantecompra",
            old_name="xml_url",
            new_name="xml_constancia",
        ),
        migrations.AddField(
            model_name="comprobantecompra",
            name="xml_comprobante",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="comprobantecompra",
            name="pdf_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
