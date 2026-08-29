# Plan: Toggle deleted view also un-deletes (flip boolean only)

## Context
`ToggleUserDeletedAPIView` (`apps/user/views.py:515`) already flips `is_deleted` and
`is_active`. Según confirmación del usuario, al deseliminar **solo se invierte el booleano**;
no se restauran username/first_name (quedan como `is_deleted_{id}`). No se requieren
cambios de schema.

## Decisiones
- Un-delete = `is_deleted = False` + `is_active = True`. Mantener username renombrado.
- Sin campos backup, sin migración.

## Tareas
1. Verificar que `ToggleUserDeletedAPIView` ya cubre ambos sentidos:
   - `value` explícito: `PATCH /usuarios/toggle-deleted/<id>/` con `{"is_deleted": false}`.
   - Sin `value`: invierte el estado actual (`not user.is_deleted`).
   Ya implementado en `apps/user/views.py:534-546`. No requiere edición.
2. Confirmar que un usuario `is_deleted=True` puede ser recuperado para deseliminarlo:
   - El listado `GetAllUsersAPIView` excluye `is_deleted` para admin_tienda, pero el
     **superuser** los ve (filtro sin `is_deleted=False`). Por tanto el superuser puede
     localizar el id y llamar al toggle para deseliminar.
   - Si se desea que admin_tienda también pueda deseliminar, habría que exponer los
     `is_deleted` en su listado (fuera de alcance según pedido previo: admin solo ve
     activos/desactivados, no eliminados). Dejar igual.
3. Ejecutar `python manage.py check` para validar que no hay errores de import/sintaxis.

## Validación
- `PATCH /usuarios/toggle-deleted/<id>/` con `{"is_deleted": true}` → `is_deleted=true`, `is_active=false`, username=`is_deleted_{id}`.
- Mismo endpoint con `{"is_deleted": false}` → `is_deleted=false`, `is_active=true` (username se conserva).
- `python manage.py check` sin errores.

## Riesgos
- Username queda como `is_deleted_{id}` tras deseliminar (aceptado por el usuario).
- Solo superuser puede reencontrar usuarios ya eliminados para deseliminarlos.
