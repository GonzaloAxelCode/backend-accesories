# Plan: Enviar `tipo_style_boleta_pdf` al backend SUNAT PHP

## Contexto

El usuario pidió "ahora envia tipo_style_boleta_pdf a sunat php". Tras inspeccionar el código:

- `apps/tienda/models.py:34` define `Tienda.tipo_style_boleta_pdf` (`CharField`, default `'default'`).
- `apps/tienda/views.py:189-216` (`UpdateTiendaStyles`) actualmente solo acepta `tipo_style_boleta_ticket` y `tipo_style_factura_pdf`; cuando llega `tipo_style_factura_pdf` también sincroniza `tipo_style_boleta_pdf` a ese mismo valor (línea 211).
- `apps/venta/utils.py:738-740` (`SunatService.build_comprobante_data`) ya incluye `tipo_style_boleta_pdf` en el payload enviado a `boleta-post.php` / `factura-post.php`.
- `apps/comprobante/views.py:220-222` (`RegistrarNotaCreditoView`) ya incluye `tipo_style_boleta_pdf` en el payload enviado a `nota-credito-post.php`.

**Hallazgo:** el campo ya se envía al PHP de SUNAT en los tres endpoints (`boleta`, `factura`, `nota crédito`). El problema real probable es que el valor que llega nunca es editable de forma independiente: `UpdateTiendaStyles` siempre lo fuerza a `tipo_style_factura_pdf`, por lo que la tienda no puede tener un diseño PDF distinto para boleta vs. factura.

## Objetivo

Garantizar que `tipo_style_boleta_pdf` se persista con el valor que la tienda elija (independiente de `tipo_style_factura_pdf`) y se envíe tal cual al backend SUNAT PHP en cada tipo de comprobante.

## Decisiones

1. **Alcance:** editar `UpdateTiendaStyles` en `apps/tienda/views.py` para que `tipo_style_boleta_pdf` sea actualizable de forma independiente. No se requieren migraciones (el campo ya existe en la tabla).
2. **Envío al PHP:** sin cambios estructurales; ya se serializa en `SunatService.build_comprobante_data` y en `RegistrarNotaCreditoView`. Verificar que en ambos casos la clave del JSON se llame exactamente `tipo_style_boleta_pdf` (lo está).
3. **Validación:** aceptar solo valores permitidos (`default`, `clasico`, `moderno`, `minimalista` u otro set acordado con SUNAT PHP). Si el PHP rechaza valores desconocidos, la tienda debe poder enviar el mismo string que el PHP espera; por defecto, aceptar cualquier `str` no vacío y de largo <= `max_length=100`.

## Cambios

### 1. `apps/tienda/views.py` — `UpdateTiendaStyles`

- Aceptar también `tipo_style_boleta_pdf` en `request.data`.
- Validación: si llega `tipo_style_boleta_pdf`, debe ser `str` no vacía y `len <= 100`. Si no, devolver `400`.
- Si llega el campo, asignar `tienda.tipo_style_boleta_pdf = tipo_style_boleta_pdf`.
- **Eliminar la sincronización** de la línea 211 (`tienda.tipo_style_boleta_pdf = tipo_style_factura_pdf`) para que cada campo sea independiente.
- Mensaje de error de "campo requerido" debe listar los tres campos.

Diff conceptual (no aplicar, solo referenciar):

```python
tipo_style_boleta_ticket = request.data.get('tipo_style_boleta_ticket')
tipo_style_boleta_pdf = request.data.get('tipo_style_boleta_pdf')
tipo_style_factura_pdf = request.data.get('tipo_style_factura_pdf')

if all(v in (None, '') for v in (tipo_style_boleta_ticket, tipo_style_boleta_pdf, tipo_style_factura_pdf)):
    return Response({"error": "Debes enviar 'tipo_style_boleta_ticket', 'tipo_style_boleta_pdf' o 'tipo_style_factura_pdf'."}, status=400)

for nombre, valor in (
    ('tipo_style_boleta_ticket', tipo_style_boleta_ticket),
    ('tipo_style_boleta_pdf', tipo_style_boleta_pdf),
    ('tipo_style_factura_pdf', tipo_style_factura_pdf),
):
    if valor in (None, ''):
        continue
    if not isinstance(valor, str) or len(valor) > 100:
        return Response({"error": f"'{nombre}' debe ser string de máximo 100 caracteres."}, status=400)
    setattr(tienda, nombre, valor)

tienda.save()
```

### 2. `apps/venta/utils.py` y `apps/comprobante/views.py`

Sin cambios funcionales: la clave `tipo_style_boleta_pdf` ya se serializa en ambos payloads. La verificación (paso de validación) consistirá en un test que confirme que el JSON enviado a la PHP contiene esa clave.

## Tareas

1. Editar `apps/tienda/views.py`:
   - Aceptar `tipo_style_boleta_pdf` en `UpdateTiendaStyles.patch`.
   - Quitar la línea que sincroniza `boleta_pdf` con `factura_pdf`.
   - Validar tipo y longitud.
2. Confirmar con `grep` que `tipo_style_boleta_pdf` aparece en:
   - `apps/venta/utils.py:739` (payload de boleta/factura).
   - `apps/comprobante/views.py:221` (payload de nota de crédito).
3. Ejecutar `python manage.py makemigrations --check --dry-run` para confirmar que no se requiere migración nueva.
4. Si existe, correr el linter configurado (ver `package.json`/`requirements.txt`/scripts del repo) sobre los archivos modificados.

## Validación

- **Unit/Manual:**
  - `POST /tienda/tiendas/styles/<id>/` con `{"tipo_style_boleta_pdf": "moderno"}` debe persistir y devolver el valor en el body.
  - `POST /tienda/tiendas/styles/<id>/` con `{"tipo_style_boleta_pdf": "moderno", "tipo_style_factura_pdf": "clasico"}` debe persistir ambos de forma independiente (antes ambos terminaban iguales).
  - Disparar una venta boleta y revisar en logs el payload a `boleta-post.php`: debe contener `"tipo_style_boleta_pdf": "moderno"`.
  - Disparar una nota de crédito y revisar el payload a `nota-credito-post.php`: debe contener `"tipo_style_boleta_pdf": "..."` con el valor actual de la tienda.
- **Regresión:** asegurar que los clientes existentes que no enviaban `tipo_style_boleta_pdf` sigan recibiendo `'default'` (default del modelo) sin cambios.

## Riesgos

- El backend PHP puede no reconocer ciertos valores de `tipo_style_boleta_pdf`; mientras no haya un catálogo acordado se acepta cualquier string de hasta 100 chars.
- Quitar la sincronización entre `boleta_pdf` y `factura_pdf` cambia comportamiento: tiendas que dependían del valor acoplado ahora verán los valores divergir. Si la sincronización era intencional, mantenerla como caso por defecto (ver pregunta abierta).

## Pregunta abierta

¿La sincronización actual `tipo_style_boleta_pdf = tipo_style_factura_pdf` debe mantenerse como fallback (solo aplicar cuando `boleta_pdf` viene vacío) o eliminarse por completo?

- **Recomendado:** eliminar la sincronización; el campo se vuelve independiente, que es lo que el cambio solicitado implica.

## Out of scope

- Crear un nuevo endpoint en `apps/comprobante` para el diseño (rechazado en pregunta anterior).
- Mover el campo a `ComprobanteElectronico` (rechazado en pregunta anterior).
- Definir el catálogo de valores válidos que el PHP acepta (depende del PHP, no del backend Django).
