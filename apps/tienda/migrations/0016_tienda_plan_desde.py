# Inicio del periodo vigente del plan (ventana de 30 días corridos)
from django.db import migrations, models
from django.utils import timezone


def backfill_plan_desde(apps, schema_editor):
    Tienda = apps.get_model("tienda", "Tienda")
    ahora = timezone.now()
    for tienda in Tienda.objects.filter(plan__isnull=False, plan_desde__isnull=True):
        tienda.plan_desde = tienda.date_created or ahora
        tienda.save(update_fields=["plan_desde"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tienda", "0015_plansuscripcion_precio_anual"),
    ]

    operations = [
        migrations.AddField(
            model_name="tienda",
            name="plan_desde",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Inicio del periodo vigente del plan (ventana de 30 días corridos)",
            ),
        ),
        migrations.RunPython(backfill_plan_desde, noop),
    ]
