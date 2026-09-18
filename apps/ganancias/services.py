"""Lógica de ganancias SIN modelo y SIN conexión directa a BD.

Todo opera sobre el snapshot `productos_json` de cada Venta:

- precio de venta unitario (ya con descuento aplicado):
  `precio_unitario` -> fallback `precio_venta` / `costo_original`
- precio de compra unitario:
  `precio_compra` -> fallback `costo_compra`
- cantidad: `cantidad`

NO se toca IGV por pedido explícito. Fórmula única:

    venta_item   = precio_venta_unitario * cantidad
    costo_item   = precio_compra_unitario * cantidad
    ganancia     = venta_item - costo_item   (soles)
    margen_venta = ganancia / venta_item * 100   (si venta_item > 0)
    markup_costo = ganancia / costo_item * 100   (si costo_item > 0)

Si el item no tiene precio de compra válido se marca como
`sin_costo` y NO entra al cálculo (evita falsos 100% de margen).
"""

from apps.venta.utils import (
    _get_cantidad_safe,
    _get_precio_unitario_safe,
    _parse_productos_json,
)


def get_precio_compra_safe(item):
    """Extrae precio de compra unitario como float o None si no existe."""
    raw = item.get("precio_compra")
    if raw in (None, ""):
        raw = item.get("costo_compra")
    if raw in (None, ""):
        return None
    try:
        valor = float(raw)
    except (ValueError, TypeError):
        try:
            valor = float(str(raw).replace(",", "."))
        except Exception:
            return None
    if valor <= 0:
        return None
    return valor


def get_nombre_producto(item):
    nombre = (
        item.get("producto_nombre")
        or item.get("nombre")
        or item.get("descripcion")
        or "Sin nombre"
    )
    nombre = str(nombre).strip()
    return nombre or "Sin nombre"


def ganancia_por_item(item):
    """Calcula ganancia de un item de productos_json.

    Retorna dict con venta, costo, ganancia, margen o None si se ignora.
    """
    if not isinstance(item, dict):
        return None
    cantidad = _get_cantidad_safe(item)
    if cantidad is None:
        return None
    precio_venta = _get_precio_unitario_safe(item, cantidad)
    precio_compra = get_precio_compra_safe(item)
    if precio_compra is None:
        return {
            "calculable": False,
            "cantidad": cantidad,
            "precio_venta": round(precio_venta, 2),
            "precio_compra": None,
        }
    venta = round(precio_venta * cantidad, 2)
    costo = round(precio_compra * cantidad, 2)
    ganancia = round(venta - costo, 2)
    margen = round((ganancia / venta) * 100, 2) if venta > 0 else 0.0
    markup = round((ganancia / costo) * 100, 2) if costo > 0 else 0.0
    return {
        "calculable": True,
        "cantidad": cantidad,
        "precio_venta": round(precio_venta, 2),
        "precio_compra": round(precio_compra, 2),
        "venta": venta,
        "costo": costo,
        "ganancia": ganancia,
        "margen": margen,
        "markup": markup,
    }


def ganancia_por_venta(productos_json):
    """Agrega venta/costo/ganancia de una venta completa."""
    total_venta = 0.0
    total_costo = 0.0
    items_ok = 0
    items_sin_costo = 0
    for item in _parse_productos_json(productos_json):
        r = ganancia_por_item(item)
        if r is None:
            continue
        if not r["calculable"]:
            items_sin_costo += 1
            continue
        total_venta += r["venta"]
        total_costo += r["costo"]
        items_ok += 1
    total_venta = round(total_venta, 2)
    total_costo = round(total_costo, 2)
    ganancia = round(total_venta - total_costo, 2)
    margen = round((ganancia / total_venta) * 100, 2) if total_venta > 0 else 0.0
    return {
        "total_venta": total_venta,
        "total_costo": total_costo,
        "ganancia": ganancia,
        "margen": margen,
        "items_ok": items_ok,
        "items_sin_costo": items_sin_costo,
    }
