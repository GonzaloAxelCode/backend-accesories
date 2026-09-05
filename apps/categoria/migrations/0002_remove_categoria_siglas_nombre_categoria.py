from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('categoria', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='categoria',
            name='siglas_nombre_categoria',
        ),
    ]
