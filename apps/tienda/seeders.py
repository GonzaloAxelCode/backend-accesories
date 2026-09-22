"""Seeders idempotentes de planes de suscripción (portables a cualquier BD).

Todo pasa por el ORM: no hay SQL crudo, así que funciona igual en
Postgres, SQLite o MySQL. Se ejecuta automáticamente al crear un
superusuario (ver ``UserManager.create_superuser``) y manualmente con::

    python manage.py seed_planes
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

PLAN_DEMO_NOMBRE = "Demo"

# "Ilimitado" no puede ser 0: en get_estado_limites el límite 0 bloquea
# (fail-closed) y la comparación es uso >= límite. Se usa un centinela alto.
ILIMITADO = 999999

PLANES_INICIALES = [
    {
        "nombre_plan": "Demo",
        "descripcion": "Plan Demo para pruebas",
        "lista_descripcion": [
            "Gratis prueba demo",
            "1 personal",
            "20 facturas",
            "10 boletas",
            "50 productos",
        ],
        "limite_boletas": 10,
        "limite_facturas": 20,
        "limite_personal": 1,
        "limite_productos": 50,
        "precio_mensual": Decimal("0.00"),
        "precio_anual": Decimal("0.00"),
    },
    {
        "nombre_plan": "Básico",
        "descripcion": "Ideal para una tienda pequeña que recién empieza",
        "lista_descripcion": [
            "100 boletas",
            "100 facturas",
            "4 personales",
            "200 productos",
            "Soporte técnico primer mes",
        ],
        "limite_boletas": 100,
        "limite_facturas": 100,
        "limite_personal": 4,
        "limite_productos": 200,
        "precio_mensual": Decimal("29.90"),
        "precio_anual": Decimal("358.80"),
    },
    {
        "nombre_plan": "Estándar",
        "descripcion": "Para tiendas con ventas constantes",
        "lista_descripcion": [
            "400 boletas",
            "400 facturas",
            "Hasta 3 sucursales",
            "Soporte técnico los primeros 3 meses",
            "500 productos",
        ],
        "limite_boletas": 400,
        "limite_facturas": 400,
        "limite_personal": 8,
        "limite_productos": 500,
        "precio_mensual": Decimal("39.90"),
        "precio_anual": Decimal("478.80"),
    },
    {
        "nombre_plan": "Pro",
        "descripcion": "Para tiendas con alto volumen de ventas",
        "lista_descripcion": [
            "1000 boletas",
            "1000 facturas",
            "15 personales",
            "Soporte 1 año",
            "Productos ilimitados",
            "Instalación gratis",
        ],
        "limite_boletas": 1000,
        "limite_facturas": 1000,
        "limite_personal": 15,
        "limite_productos": ILIMITADO,
        "precio_mensual": Decimal("69.90"),
        "precio_anual": Decimal("838.80"),
    },
    {
        "nombre_plan": "Premium",
        "descripcion": "Sin restricciones prácticas de volumen",
        "lista_descripcion": [
            "10000 boletas",
            "10000 facturas",
            "Personal ilimitado",
            "Instalación gratis",
            "Soporte técnico de por vida",
            "Productos ilimitados",
            "Todos los módulos habilitados",
            "Actualizaciones gratis",
            "Capacitación programada",
        ],
        "limite_boletas": 10000,
        "limite_facturas": 10000,
        "limite_personal": 100,
        "limite_productos": ILIMITADO,
        "precio_mensual": Decimal("99.90"),
        "precio_anual": Decimal("1198.80"),
    },
]


def seed_planes(using=None):
    """Crea/actualiza los planes iniciales y asigna Demo a tiendas sin plan.

    Idempotente: se puede correr N veces sin duplicar. Usa
    ``update_or_create`` para que cambios de precios/límites en el código
    se propaguen a la BD.
    """
    from .models import PlanSuscripcion, Tienda

    planes_qs = PlanSuscripcion.objects.using(using) if using else PlanSuscripcion.objects
    tiendas_qs = Tienda.objects.using(using) if using else Tienda.objects

    creados = 0
    actualizados = 0
    with transaction.atomic(using=using):
        for datos in PLANES_INICIALES:
            datos = dict(datos)
            nombre = datos.pop("nombre_plan")
            _, created = planes_qs.update_or_create(
                nombre_plan=nombre,
                defaults={**datos, "moneda": "PEN", "activo": True},
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        # Todas las tiendas sin plan quedan con Demo (incluye la tienda
        # del superusuario recién creado). No toca tiendas con plan pago.
        demo = planes_qs.get(nombre_plan=PLAN_DEMO_NOMBRE)
        tiendas_actualizadas = tiendas_qs.filter(plan__isnull=True).update(
            plan=demo, plan_desde=timezone.now()
        )

    return {
        "creados": creados,
        "actualizados": actualizados,
        "tiendas_con_demo": tiendas_actualizadas,
    }
