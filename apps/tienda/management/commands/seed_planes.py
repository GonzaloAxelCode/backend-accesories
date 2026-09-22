from django.core.management.base import BaseCommand

from apps.tienda.seeders import seed_planes


class Command(BaseCommand):
    help = (
        "Crea/actualiza los planes de suscripción iniciales "
        "(Demo, Básico, Estándar, Pro, Premium) y asigna el plan Demo "
        "a todas las tiendas que no tengan plan."
    )

    def handle(self, *args, **options):
        resumen = seed_planes()
        self.stdout.write(
            self.style.SUCCESS(
                "Planes: %(actualizados)d existentes actualizados, "
                "%(creados)d creados. Tiendas con Demo: %(tiendas_con_demo)d."
                % resumen
            )
        )
