# Plan: Superuser vea tiendas eliminadas en GetAllTiendas

## Context
En `GetAllTiendas` (`apps/tienda/views.py:20`), la rama de superuser usa
`Tienda.objects.filter(is_deleted=False)` (`apps/tienda/views.py:27`), por lo que **excluye**
las tiendas con `is_deleted=True`. El usuario confirmó que en local y producción usa la misma
cuenta superuser (`id=1`, `is_superuser=true`), y que en producción hay tiendas eliminadas que
no aparecen, mientras local no tiene eliminadas (por eso "trae todas" en local y no en prod).
Decisión: el superuser debe ver el panorama completo, incluidas las `is_deleted=True`, coherente
con *"la agrupación de tiendas es solo para superusuario"*.

## Decisión
- **Superuser:** devolver TODAS las tiendas, sin filtrar por `is_deleted`.
- **admin_tienda:** mantener el comportamiento actual (solo `is_deleted=False`: su tienda +
  sucursales + donde es propietario).

## Tareas
1. En `apps/tienda/views.py`, método `GetAllTiendas.get`:
   - Cambiar la línea 27:
     `tiendas = Tienda.objects.filter(is_deleted=False)`
     por:
     `tiendas = Tienda.objects.all()`
   - La rama de admin_tienda (líneas 28-40) queda igual (mantiene `is_deleted=False`).
2. El `TiendaSerializer` ya incluye `is_deleted` (campo del modelo, `fields='__all__`), así el
   frontend puede distinguir tiendas activas de eliminadas. No requiere cambios de serializer.
3. No se requiere migración (solo lógica de consulta).

## Validación
- `python manage.py check` sin errores.
- Con superuser: `GET /api/tiendas/` devuelve tiendas con `is_deleted=true` y `false`.
- Con admin_tienda: `GET /api/tiendas/` sigue devolviendo solo su tienda + sucursales
  (`is_deleted=False`).
- Confirmar en producción que ahora aparecen las tiendas previamente ocultas por `is_deleted`.

## Riesgos
- El listado de superuser crecerá con tiendas eliminadas; el frontend debe manejarlas (p. ej.
  atenuarlas o filtrarlas en UI). El campo `is_deleted` ya viaja en la respuesta.
- No afecta a `GetTienda`, `GetMiTiendaView` ni a la creación/edición.
