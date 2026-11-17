# Generated to scope predefinidas per-tienda (admin fix)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('categoria', '0004_categoria_tipo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categoria',
            name='nombre',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddConstraint(
            model_name='categoria',
            constraint=models.UniqueConstraint(fields=('tienda', 'nombre'), name='uq_categoria_tienda_nombre'),
        ),
    ]
