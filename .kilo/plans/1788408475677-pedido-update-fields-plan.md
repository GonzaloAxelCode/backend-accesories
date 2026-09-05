# Plan: Vista genérica para actualizar `estado`, `estado_pago` y `prioridad` de un pedido

## Objetivo
Modificar `MarcarPedidoPagadoView` (apps/pedidos/views.py) para que el body solo actualizar los campos `estado`, `estado_pago` y `prioridad`, aceptando opcionalmente cualquier subconjunto de ellos. Si el campo llega ausente o vacío, NO se actualiza ese campo.

## Endpoint
`PUT /api/pedidos/<int:pedido_id>/pagar/` (ruta ya registrada en apps/pedidos/urls.py:11)

## Body aceptado (todos opcionales, ninguno obligatorio)
```json
{
  "estado": "CONFIRMADO",
  "estado_pago": "PAGADO",
  "prioridad": "URGENTE"
}
```
- Si una clave **no viene** en el JSON, o viene con valor `""` / `null`, se **ignora** (no se modifica el campo en BD).
- Si viene un valor no vacío, se valida contra las choices del modelo y se persiste.

## Reglas de validación (reutilizando choices del modelo Pedido)
- `estado` ∈ `{COTIZADO, PENDIENTE, CONFIRMADO, EN_PREPARACION, LISTO, ENTREGADO, CANCELADO}`
- `estado_pago` ∈ `{PENDIENTE, PARCIAL, PAGADO}`
- `prioridad` ∈ `{NORMAL, URGENTE}`

Reglas de negocio adicionales (alineadas con `ConfirmarEstadoPedidoView` y `CancelarPedidoView`):
- Si `pedido.estado == 'CANCELADO'` → 400 "No se puede modificar un pedido cancelado".
- Si `pedido.estado == 'ENTREGADO'` → 400 "No se puede modificar un pedido ya entregado" (sólo para `estado`; permitir `estado_pago`/`prioridad` si el pedido está entregado? Ver pregunta abierta).

## Cambios

### apps/pedidos/views.py
Renombrar/reutilizar la vista existente `MarcarPedidoPagadoView` para que sea genérica. Cambiar:
- Quitar la asignación directa `pedido.estado_pago = 'PAGADO'`.
- Por cada clave presente y no vacía en `request.data`:
  - Si la clave es `estado`, `estado_pago` o `prioridad`, validar contra las choices.
  - Si es válida, setear el atributo en `pedido`.
- Dejar de forzar `monto_adelanto = pedido.total` cuando no se envía `monto`.
- `pedido.save()` solo si al menos un campo fue modificado (o siempre, según preferencia; ver pregunta abierta).

### apps/pedidos/urls.py
Mantener el nombre de la vista/URL (`pagar-pedido`) para evitar romper consumidores existentes. Opcionalmente renombrar a algo más genérico como `actualizar-campos-pedido` (ver pregunta abierta).

## Respuesta
Devolver 200 con la representación resumida del pedido tras los cambios:
```json
{
  "mensaje": "Pedido actualizado",
  "pedido": {
    "id": ...,
    "numero_pedido": ...,
    "estado": ...,
    "estado_pago": ...,
    "prioridad": ...,
    "total": ...,
    "nombre_cliente": ...
  }
}
```

## Validación
- Probar: body vacío `{}` → 200 sin cambios.
- Probar: `{"estado_pago": ""}` → 200 sin cambios.
- Probar: `{"estado": "CONFIRMADO"}` → 200, cambia solo `estado`.
- Probar: `{"estado": "INVALIDO"}` → 400.
- Probar: `{"estado_pago": "PAGADO", "prioridad": "URGENTE"}` → 200, ambos campos.

## Preguntas abiertas
1. ¿Si el pedido está `ENTREGADO`, se debe permitir actualizar `estado_pago`/`prioridad`? Recomendado: **bloquear cualquier cambio** si está ENTREGADO o CANCELADO, consistente con `ConfirmarEstadoPedidoView`.
2. ¿Renombrar la URL `pagar-pedido` a algo más genérico (ej. `actualizar-campos-pedido`)? Recomendado: **sí**, para reflejar el nuevo alcance.
3. ¿Devolver 200 aunque ningún campo haya cambiado, o 400 si no hay nada que actualizar? Recomendado: **200** (idempotente, sin error).