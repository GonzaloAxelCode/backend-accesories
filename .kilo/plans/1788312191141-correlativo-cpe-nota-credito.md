# Plan: Numeración de comprobantes electrónicos (CPE/NC) sin duplicados + fix de serie NC

## Contexto (lo que hay hoy)

- `apps/comprobante/models.py`
  - `ComprobanteElectronico` (line 8) tiene `tipo_comprobante CharField(10)` libre con valores `"Factura"` o `"Boleta"`, más `serie CharField(4)` (`B001`/`F001`) y `correlativo CharField(8)` (`00000001`).
  - `NotaCreditoDB` (line 53) usa `tipo_comprobante_modifica CharField(2)` con catálogo SUNAT (`01`/`03`), `serie CharField(10)`, `correlativo CharField(8)`.
- `apps/venta/utils.py:524-549` `ComprobanteService.get_siguiente(tipo_comprobante, tienda)` calcula serie y correlativo del CPE leyendo el último `ComprobanteElectronico` de la tienda. **Sin `select_for_update` ni unique constraint** → bajo concurrencia dos ventas pueden leer el mismo último correlativo y duplicar.
- `apps/venta/utils.py:552-580` `get_siguiente_nota_credito(...)` usa el mismo patrón con `NotaCreditoDB` y además **arma la serie con prefijo `F`/`B`** (`F001`, `B001`). SUNAT exige series **`FC01`** para NC de factura y **`BC01`** para NC de boleta, y la numeración corre independiente del CPE.
- `apps/venta/views.py:101-127` `CreateSaleView.post` invoca `get_siguiente`, crea el CPE con `estado_sunat="PENDIENTE"` y luego llama al PHP fuera del `atomic`. Si el PHP rechaza, el correlativo ya queda consumido en BD.
- `apps/comprobante/views.py:180-202` `RegistrarNotaCreditoView.post` ya llama a `get_siguiente_nota_credito` y envía `tipo_comprobante: "07"` al PHP, pero la serie está mal construida.
- `apps/venta/utils.py:712-717` `get_php_url` enruta según `"Factura"`/`"Boleta"`, no por código SUNAT.
- `apps/venta/sunat.py` es código legacy con varios bugs tipográficos (`self-responseSunat`, `comprobante_` mal escritos, `self.omprobante`, `self.comprobante_`). **Fuera de alcance de este plan**: solo se documenta.

## Decisiones de diseño (a confirmar antes de ejecutar)

1. **Catálogo de tipo de comprobante** dentro del backend
   - Crear `TIPO_CPE = {"FACTURA": "01", "BOLETA": "03", "NOTA_CREDITO": "07", "NOTA_DEBITO": "08", "GRE": "09"}` en `apps/venta/catalogs.py` (nuevo). Mantener `ComprobanteElectronico.tipo_comprobante` como el nombre legible y agregar `tipo_codigo` con `choices` del catálogo. Backfill desde valores existentes.
   - Razón: el PHP espera `01/03/07/09`; el código de negocio en views usa `"Factura"/"Boleta"`. No romper llamadas internas.

2. **Series de Nota de Crédito** (fix de bug)
   - Serie NC de factura → `F<serie-tienda>C01` (ej. `F001C01`).
   - Serie NC de boleta → `B<serie-tienda>C01` (ej. `B001C01`).
   - Esto es lo que SUNAT valida. Reemplazar la lógica de `get_siguiente_nota_credito` (utils.py:552-580).

3. **Numeración atómica**
   - Estrategia: `SELECT … FOR UPDATE` sobre la fila de `Tienda` para serializar las ventas de una misma tienda durante el cálculo del siguiente correlativo. Mantener la lectura del último comprobante (vía `Coalesce(Max('correlativo'), 0)`) dentro de la misma transacción. No requiere migrar a una tabla de numeradores (más simple y suficiente para el volumen actual).
   - Alternativa descartada por ahora: tabla `NumeracionTienda`. Se deja como upgrade futuro.

4. **Reversibilidad del correlativo consumido cuando SUNAT rechaza**
   - Hoy el `ComprobanteElectronico` con `estado_sunat="PENDIENTE"` se crea antes del POST al PHP, y nunca se borra si SUNAT lo rechaza (queda como "PENDIENTE"/"RECHAZADO"). El correlativo queda "quemado" para SUNAT aunque no se haya emitido.
   - Decisión: **mantener el correlativo consumido** (es la postura segura: SUNAT no permite huecos en series activas). Se documenta y se cambia la regla: si el POST al PHP falla por timeout/conexión, dejamos el CPE en `estado_sunat="ERROR"` y se permite reintento manual (re-uso del mismo correlativo, mismo `comprobante.id`).
   - Si se requiere re-emitir un CPE después de un rechazo de SUNAT, se crea un nuevo comprobante con el siguiente correlativo (no se reutiliza el número).

5. **Alcance**: solo CPE (Factura/Boleta) y NC. **GRE queda fuera de alcance** en esta iteración.

## Cambios a realizar

### A. Nuevo módulo de catálogos
- `apps/venta/catalogs.py` (nuevo) con:
  - `TIPO_CPE` (dict nombre→código SUNAT).
  - `TIPO_DOC_CLIENTE` (0, 1, 4, 6, 7).
  - `SERIE_NC_PREFIJO = {"01": "FC01", "03": "BC01"}` (mapeo de tipo de comprobante modificado a prefijo de serie NC).
  - `tipo_a_codigo(nombre: str) -> str` helper que normaliza (`"Factura".lower() == "factura"` → `"01"`).

### B. Migración de modelo
- `apps/comprobante/migrations/XXXX_alter_*.py`:
  - `ComprobanteElectronico`:
    - Cambiar `tipo_comprobante` a `CharField(max_length=10, choices=[("Factura","Factura"),("Boleta","Boleta")])` (no se renombra, solo choices para validar).
    - Agregar `tipo_codigo = CharField(max_length=2, choices=[("01","Factura"),("03","Boleta"),("07","Nota de crédito"),("08","Nota de débito"),("09","GRE")])`.
    - Agregar `UniqueConstraint(fields=["tienda_no", "tipo_codigo", "serie", "correlativo"], name="uq_cpe_tienda_tipo_serie_corr")`. **Pero `ComprobanteElectronico` no tiene FK a tienda** (la hereda vía `venta__tienda`). **Decisión técnica**: o se agrega `tienda = ForeignKey(Tienda, ...)` denormalizado (con backfill), o el constraint se valida en servicio. Elegir **denormalizar** `tienda` en `ComprobanteElectronico` y `NotaCreditoDB` (más simple para el unique constraint y para los `select_for_update`).
  - `NotaCreditoDB`: agregar `tienda = ForeignKey(Tienda, on_delete=PROTECT, null=True, related_name="notas_credito")` con backfill desde `venta__tienda`. Mismo UniqueConstraint.

### C. `ComprobanteService` en `apps/venta/utils.py`
- Reescribir `get_siguiente(tipo_comprobante, tienda)`:
  - Tomar `Tienda.objects.select_for_update().get(pk=tienda.pk)` para serializar.
  - `ultimo_correlativo = Coalesce(Max("correlativo_int"), Value(0))` filtrado por `tienda, tipo_codigo, serie`. Para esto, **agregar `correlativo_int = PositiveIntegerField(null=True, blank=True)`** y backfill desde `correlativo` (string).
  - `nuevo = ultimo + 1`, devolver `(serie, str(nuevo).zfill(8))`.
  - `get_siguiente_nota_credito(...)`: usar `SERIE_NC_PREFIJO[tipo_codigo]` + `tienda.serie` → `F<serie>C01`/`B<serie>C01`. Misma estrategia de locking.

### D. `CreateSaleView.post` (`apps/venta/views.py`)
- Mover `get_siguiente` y la creación del `ComprobanteElectronico` **dentro del `transaction.atomic()`** que ya existe. (Hoy ya está adentro, pero el `send_to_sunat` se hace fuera — eso está bien).
- Si SUNAT rechaza o falla la conexión → estado `RECHAZADO`/`ERROR`, el correlativo se mantiene.

### E. `RegistrarNotaCreditoView.post` (`apps/comprobante/views.py:180-202`)
- Cambiar la determinación de `tipo_comprobante_modifica` para usar el helper `tipo_a_codigo`.
- Llamar a `get_siguiente_nota_credito` con la firma actualizada.
- Mantener el orden: `select_for_update(Tienda)` → calcular serie/correlativo → POST al PHP → `transaction.atomic` para guardar NC + devolver stock.

### F. `SunatService.get_php_url` (`apps/venta/utils.py:712-717`)
- Aceptar `tipo_codigo` (`"01"`/`"03"`) y mapear: `01 → factura-post.php`, `03 → boleta-post.php`. Mantener compatibilidad pasando el string viejo.

### G. Backfill / data migration
- Script `apps/comprobante/migrations/XXXX_backfill_*.py`:
  - `ComprobanteElectronico.tipo_codigo` desde `tipo_comprobante` (`Factura→01`, `Boleta→03`).
  - `ComprobanteElectronico.correlativo_int` desde `int(correlativo)`.
  - `ComprobanteElectronico.tienda` desde `venta.tienda`.
  - Idem para `NotaCreditoDB`.

## Plan de validación

1. **Unit tests** (`apps/venta/tests/test_correlativo.py`, nuevo):
   - 100 ventas concurrentes con `ThreadPoolExecutor` sobre la misma tienda/tipo → todos los correlativos únicos, sin huecos, en orden.
   - Serie NC correcta: NC sobre factura → `F001C01-00000001`; NC sobre boleta → `B001C01-00000001`.
   - `get_siguiente` devuelve correlativo_inicial cuando la tabla está vacía.
2. **Tests de rechazo SUNAT**:
   - Stub del PHP que devuelve 400 → `ComprobanteElectronico.estado_sunat="RECHAZADO"`, el correlativo siguiente no se ve afectado (el siguiente `get_siguiente` salta el rechazado).
3. **Migración reversible**: probar `migrate`/`migrate <prev>` en una BD de staging.

## Archivos a tocar (resumen)

- Nuevos: `apps/venta/catalogs.py`, `apps/venta/tests/test_correlativo.py`.
- Editar:
  - `apps/comprobante/models.py`
  - `apps/venta/utils.py` (`ComprobanteService.get_siguiente*`, `SunatService.get_php_url`)
  - `apps/venta/views.py` (`CreateSaleView`)
  - `apps/comprobante/views.py` (`RegistrarNotaCreditoView`)
- Migraciones: 2 migraciones de schema + 1 de data.

## Riesgos

- **Lock de Tienda**: serializa TODAS las ventas de una tienda. Con `select_for_update` y transacciones cortas el impacto es bajo, pero si la venta tarda varios segundos el resto de usuarios de la misma tienda esperará. Mitigación: la transacción actual ya es corta; `send_to_sunat` ya está fuera del `atomic`.
- **Datos históricos**: BD en producción puede tener `tipo_comprobante` con valores distintos a `Factura`/`Boleta`. El backfill debe tolerar mayúsculas/minúsculas y valores nulos (dejarlos como `00`/`DESCONOCIDO` y excluirlos del unique constraint).
- **GRE fuera de alcance**: si en el futuro se agrega, requerirá serie `T###` o `V###` y otro correlador independiente.

## Preguntas abiertas / confirmaciones pendientes

- ¿Confirmas que **el campo `tipo_comprobante` debe migrarse a choices + agregar `tipo_codigo`** con catálogo SUNAT? (Recomendado: sí.)
- ¿Confirmas que el **correlativo "quemado" en caso de rechazo de SUNAT no se devuelve/reusa**? (Recomendado: sí, es la postura segura.)
- ¿Confirmas que la **estrategia de locking es `select_for_update` sobre Tienda** (no tabla de numeradores)? (Recomendado: sí, por simplicidad.)
