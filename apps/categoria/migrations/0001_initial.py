# Generated manually for Categoria model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tienda', '0001_initial'),  # depende de Tienda porque usas ForeignKey
    ]

    operations = [
        migrations.CreateModel(
            name="Categoria",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=100)),
                ("descripcion", models.TextField()),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("activo", models.BooleanField(default=True)),
                ("imagen", models.ImageField(upload_to="categorias/", null=True, blank=True)),
                ("slug", models.SlugField(unique=True)),
                ("orden", models.IntegerField(default=0)),
                ("destacado", models.BooleanField(default=False)),
                ("color", models.CharField(max_length=50, blank=True)),
                ("siglas_nombre_categoria", models.CharField(max_length=10, blank=True, null=True)),
                (
                    "parent",
                    models.ForeignKey(
                        "self",
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "tienda",
                    models.ForeignKey(
                        "tienda.Tienda",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="categorias",
                        null=True,
                        blank=True,
                    ),
                ),
            ],
        ),
    ]
