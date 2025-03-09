# Generated by Django 5.1.2 on 2025-02-09 06:34

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Cliente",
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
                ("apellido", models.CharField(max_length=100)),
                (
                    "dni",
                    models.CharField(
                        blank=True, max_length=100, null=True, unique=True
                    ),
                ),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("telefono", models.CharField(max_length=15)),
                ("direccion", models.TextField()),
                ("pais", models.CharField(max_length=100)),
                ("codigo_postal", models.CharField(max_length=10)),
                ("fecha_registro", models.DateTimeField(auto_now_add=True)),
                ("fecha_nacimiento", models.DateField(blank=True, null=True)),
                (
                    "genero",
                    models.CharField(
                        choices=[("M", "Masculino"), ("F", "Femenino")], max_length=1
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
        ),
    ]
