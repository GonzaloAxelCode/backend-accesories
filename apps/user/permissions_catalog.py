"""Catálogo único de permisos del sistema.

Single source of truth: agrupa los permisos por módulo con su etiqueta
en español y deriva ALL_PERMISSIONS. Usado por:
- apps/user/models.py (Meta.permissions)
- apps/user/views.py (respuestas de permisos)
- apps/tienda/serializers.py (usuarios enriquecidos)
- core/permissions.py (clases de enforcement)

Reglas del catálogo:
- Sin permisos de "Ver", salvo Ver ganancias.
- Inventario es un solo grupo para accesorios y repuestos.
- Sin grupos de Categorías, Proveedores, Tienda ni Usuarios.

Para agregar un permiso nuevo: añádelo a un grupo (o crea el grupo),
crea la migración (`makemigrations`) y aplícala (`migrate`).
"""

PERMISSION_GROUPS = [
    {
        "id": "ventas",
        "titulo": "Ventas",
        "items": [
            ("can_make_sale", "Realizar ventas"),
            ("can_cancel_sale", "Cancelar ventas"),
        ],
    },
    {
        "id": "inventario",
        "titulo": "Inventario (accesorios y repuestos)",
        "items": [
            ("can_create_inventory", "Crear inventario"),
            ("can_modify_inventory", "Modificar inventario"),
            ("can_delete_inventory", "Eliminar inventario"),
        ],
    },
    {
        "id": "celulares",
        "titulo": "Celulares",
        "items": [
            ("can_create_celular", "Crear celulares"),
            ("can_update_celular", "Modificar celulares"),
            ("can_delete_celular", "Eliminar celulares"),
        ],
    },
    {
        "id": "compras",
        "titulo": "Compras",
        "items": [
            ("can_create_compra", "Crear compras"),
            ("can_update_compra", "Modificar compras"),
            ("can_delete_compra", "Eliminar compras"),
        ],
    },
    {
        "id": "pedidos",
        "titulo": "Pedidos / Pendientes",
        "items": [
            ("can_manage_pedido", "Gestionar pedidos pendientes"),
        ],
    },
    {
        "id": "estadisticas",
        "titulo": "Estadísticas",
        "items": [
            ("view_stats_general", "Ver estadística general"),
            ("view_stats_ventas", "Ver estadísticas de ventas"),
            ("view_stats_inventario", "Ver estadísticas de inventario"),
        ],
    },
    {
        "id": "ganancias",
        "titulo": "Ganancias",
        "items": [
            ("view_ganancia", "Ver ganancias"),
        ],
    },
    {
        "id": "exportar",
        "titulo": "Exportar datos",
        "items": [
            ("can_export_data", "Exportar datos a CSV"),
        ],
    },
    {
        "id": "backups",
        "titulo": "Backups",
        "items": [
            ("can_make_backup", "Realizar backups"),
        ],
    },
]

ALL_PERMISSIONS = [cod for g in PERMISSION_GROUPS for cod, _ in g["items"]]

#: Tuplas para Meta.permissions del modelo de usuario.
PERMISSIONS_META = [(cod, label) for g in PERMISSION_GROUPS for cod, label in g["items"]]
