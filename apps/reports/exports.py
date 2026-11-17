"""Endpoints de exportación a CSV para Exportar Datos.

Todo se filtra por mes y año (month 1-12 + year), salvo inventario
que es stock actual y el resumen anual que solo pide año:

- GET /api/reports/export/inventario/?grupo=accesorios|celulares|repuestos
- GET /api/reports/export/ventas/?month=11&year=2026
- GET /api/reports/export/ventas-mensual/?year=2026          (totales ene-dic)
- GET /api/reports/export/ganancias/?month=11&year=2026[&detalle=venta|producto]
- GET /api/reports/export/top-productos/?month=11&year=2026 (con columna Tipo: Accesorio/Celular)
- GET /api/reports/export/top-categorias/?month=11&year=2026
- GET /api/reports/export/metodos-pago/?month=11&year=2026
- GET /api/reports/export/clientes/?month=11&year=2026
- GET /api/reports/export/anuladas/?month=11&year=2026
- GET /api/reports/export/stock-bajo/                        (stock actual <= minimo)
- GET /api/reports/export/comprobantes-zip/?month=11&year=2026 (ZIP: XML + indice CSV con urls)
- GET /api/reports/export/compras-zip/?month=11&year=2026 (ZIP: XML comprobante+constancia + indice CSV con urls)

Variantes por reporte (se combinan con month/year):
- tipo=todos|accesorio|celular → ventas, ventas-mensual, ganancias, top-productos,
  top-categorias, metodos-pago, anuladas
- metodo_pago=todos|<valor> (ej: Yape) → ventas, ganancias, clientes, anuladas
- grupo=todos|accesorios|repuestos → stock-bajo
"""

import csv
from calendar import monthrange
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import PuedeExportarDatos, PuedeExportarOBackup, PuedeHacerBackup

TZ = ZoneInfo("America/Lima")
ESTADOS_VALIDOS = ["ACEPTADO", "aceptado", "Aceptado"]


def _resolver_mes(request):
    """Lee month (1-12) y year de query params. Retorna (inicio, fin) o Response de error."""
    try:
        month = int(request.query_params.get("month") or 0)
        year = int(request.query_params.get("year") or 0)
    except (ValueError, TypeError):
        return None, Response(
            {"error": "month y year deben ser números enteros"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not 1 <= month <= 12 or year < 2000:
        return None, Response(
            {"error": "month debe ser 1-12 y year un año válido"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ultimo = monthrange(year, month)[1]
    inicio = datetime(year, month, 1, 0, 0, 0, tzinfo=TZ)
    fin = datetime(year, month, ultimo, 23, 59, 59, tzinfo=TZ)
    return (inicio, fin, month, year), None


def _tipo_item(item):
    """Accesorio (todo Producto) o Celular. Se especifica siempre que se mezclan."""
    if not isinstance(item, dict):
        return "Accesorio"
    if item.get("es_celular") or item.get("celular_id") is not None:
        return "Celular"
    if item.get("imei") or item.get("imei1"):
        return "Celular"
    return "Accesorio"


def _filtro_tipo(request):
    """?tipo=todos|accesorio|celular. Retorna 'todos'|'accesorio'|'celular'."""
    t = (request.query_params.get("tipo") or "todos").lower()
    return t if t in ("accesorio", "celular") else "todos"


def _filtro_metodo(request):
    """?metodo_pago=todos|<valor>. Retorna None (sin filtro) o el valor."""
    m = (request.query_params.get("metodo_pago") or "").strip()
    return m if m and m.lower() != "todos" else None


def _sufijo_filtros(tipo="todos", metodo=None):
    """Sufijo para el nombre del archivo, ej: _celulares_yape."""
    from django.utils.text import slugify

    suf = ""
    if tipo != "todos":
        suf += f"_{tipo}"
    if metodo:
        suf += f"_{(slugify(metodo) or 'metodo').replace('-', '')}"
    return suf


def _quiere_tipo(item, tipo):
    if tipo == "todos":
        return True
    want = "Celular" if tipo == "celular" else "Accesorio"
    return _tipo_item(item) == want


def _monto_items_tipo(productos_json, tipo="todos"):
    """(monto, n_items) sumando solo items del tipo indicado."""
    from apps.venta.utils import _get_cantidad_safe, _get_precio_unitario_safe, _parse_productos_json

    total = 0.0
    n = 0
    for item in _parse_productos_json(productos_json):
        if not isinstance(item, dict):
            continue
        if not _quiere_tipo(item, tipo):
            continue
        cantidad = _get_cantidad_safe(item)
        if cantidad is None:
            continue
        total += round(_get_precio_unitario_safe(item, cantidad) * cantidad, 2)
        n += cantidad
    return round(total, 2), n


def _ganancia_venta_tipo(productos_json, tipo="todos"):
    """Como ganancia_por_venta pero solo con items del tipo indicado."""
    from apps.ganancias.services import ganancia_por_item
    from apps.venta.utils import _parse_productos_json

    if tipo == "todos":
        from apps.ganancias.services import ganancia_por_venta

        return ganancia_por_venta(productos_json)
    total_venta = total_costo = 0.0
    ok = sin = 0
    for item in _parse_productos_json(productos_json):
        if not isinstance(item, dict) or not _quiere_tipo(item, tipo):
            continue
        r = ganancia_por_item(item)
        if r is None:
            continue
        if not r["calculable"]:
            sin += 1
            continue
        total_venta += r["venta"]
        total_costo += r["costo"]
        ok += 1
    total_venta = round(total_venta, 2)
    total_costo = round(total_costo, 2)
    ganancia = round(total_venta - total_costo, 2)
    margen = round((ganancia / total_venta) * 100, 2) if total_venta > 0 else 0.0
    return {"total_venta": total_venta, "total_costo": total_costo, "ganancia": ganancia,
            "margen": margen, "items_ok": ok, "items_sin_costo": sin}


def _csv_response(header, rows, filename):
    buf = StringIO()
    buf.write("\ufeff")  # BOM para que Excel abra los tildes bien
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


class ExportInventarioView(APIView):
    permission_classes = [IsAuthenticated, PuedeHacerBackup]

    def get(self, request):
        grupo = (request.query_params.get("grupo") or "accesorios").lower()
        if grupo not in ("accesorios", "celulares", "repuestos"):
            grupo = "accesorios"
        tienda = request.user.tienda
        hoy = timezone.now().astimezone(TZ).date().isoformat()

        if grupo == "celulares":
            from apps.celular.models import Celular

            header = ["Marca", "Modelo", "Color", "Memoria", "RAM", "Estado", "IMEI1", "IMEI2",
                      "Costo compra", "Precio venta", "Disponible"]
            rows = []
            for cel in Celular.objects.filter(tienda=tienda, activo=True, is_deleted=False).order_by("marca", "modelo"):
                rows.append([cel.marca, cel.modelo, cel.color, cel.memoria, cel.ram or "",
                             cel.estado_equipo, cel.imei1, cel.imei2 or "",
                             float(cel.costo_compra or 0), float(cel.precio_venta or 0),
                             "SI" if cel.disponible else "NO"])
            return _csv_response(header, rows, f"celulares_{hoy}.csv")

        from apps.inventario.models import Inventario

        if grupo == "repuestos":
            header = ["Nombre", "Tipo", "Categoria", "SKU/Ubicacion", "Stock", "Stock min",
                      "Costo", "Costo venta", "Valorizado", "Proveedor", "Estado"]
            rows = []
            qs = Inventario.objects.filter(tienda=tienda, activo=True).select_related(
                "producto", "producto__categoria", "repuesto", "repuesto__categoria", "proveedor"
            ).order_by("producto__nombre", "repuesto__nombre")
            for inv in qs:
                es_rep = inv.repuesto_id is not None or (
                    inv.producto and getattr(getattr(inv.producto, "categoria", None), "tipo", "") == "REPUESTO"
                )
                if not es_rep:
                    continue
                nombre = inv.repuesto.nombre if inv.repuesto else (inv.producto.nombre if inv.producto else "")
                cat = ""
                if inv.repuesto and inv.repuesto.categoria:
                    cat = inv.repuesto.categoria.nombre
                elif inv.producto and inv.producto.categoria:
                    cat = inv.producto.categoria.nombre
                sku = (inv.repuesto.ubicacion if inv.repuesto and inv.repuesto.ubicacion else "") or (inv.producto.sku if inv.producto else "")
                costo = float(inv.costo or 0)
                rows.append([nombre, "Repuesto", cat, sku or (inv.ubicacion or ""), inv.cantidad, inv.stock_minimo,
                             costo, float(inv.costo_venta or 0), round(costo * (inv.cantidad or 0), 2),
                             inv.proveedor.nombre if inv.proveedor else "", inv.estado or ""])
            return _csv_response(header, rows, f"repuestos_{hoy}.csv")

        header = ["Producto", "Tipo", "SKU", "Categoria", "Marca", "Modelo", "Stock", "Stock min",
                  "Costo", "Precio venta", "Valorizado", "Ubicacion", "Proveedor"]
        rows = []
        qs = Inventario.objects.filter(tienda=tienda, activo=True).select_related(
            "producto", "producto__categoria", "proveedor"
        ).order_by("producto__nombre")
        for inv in qs:
            if inv.repuesto_id is not None:
                continue
            if inv.producto and getattr(getattr(inv.producto, "categoria", None), "tipo", "") == "REPUESTO":
                continue
            p = inv.producto
            costo = float(inv.costo or 0)
            rows.append([
                p.nombre if p else "", "Accesorio", p.sku if p else "",
                p.categoria.nombre if p and p.categoria else "",
                (p.marca if p else "") or "", (p.modelo if p else "") or "",
                inv.cantidad, inv.stock_minimo, costo, float(inv.costo_venta or 0),
                round(costo * (inv.cantidad or 0), 2), inv.ubicacion or "",
                inv.proveedor.nombre if inv.proveedor else "",
            ])
        return _csv_response(header, rows, f"accesorios_{hoy}.csv")


class ExportVentasView(APIView):
    """Detalle de ventas de un mes. ?month=1-12&year=2026[&tipo=todos|accesorio|celular][&metodo_pago=]."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)
        metodo = _filtro_metodo(request)

        qs = Venta.objects.filter(
            tienda=tienda, activo=True, fecha_hora__gte=inicio, fecha_hora__lte=fin,
        )
        if metodo:
            qs = qs.filter(metodo_pago__iexact=metodo)
        ventas = qs.select_related("comprobante", "usuario").order_by("fecha_hora")

        header = ["Fecha", "Hora", "Comprobante", "Tipo", "Cliente", "Doc cliente",
                  "Metodo pago", "Estado", "Vendedor", "Total S/"]
        rows = []
        total = 0.0
        for v in ventas:
            comp = getattr(v, "comprobante", None)
            num = f"{comp.serie}-{comp.correlativo}" if comp and comp.serie else (v.tipo_comprobante or "")
            fh = v.fecha_hora.astimezone(TZ)
            if tipo == "todos":
                monto = round(float(calcular_total_venta(v)), 2)
            else:
                monto, n_items = _monto_items_tipo(v.productos_json, tipo)
                if n_items == 0:
                    continue
            total += monto
            usuario = getattr(getattr(v, "usuario", None), "username", "") or ""
            rows.append([fh.date().isoformat(), fh.strftime("%H:%M"), num, v.tipo_comprobante or "",
                         v.nombre_cliente or "Cliente general", v.numero_documento_cliente or "",
                         v.metodo_pago or "", v.estado or "", usuario, monto])
        rows.append(["", "", "", "", "", "", "", "", "TOTAL:", round(total, 2)])
        suf = _sufijo_filtros(tipo, metodo)
        return _csv_response(header, rows, f"ventas_{year}-{month:02d}{suf}.csv")


class ExportVentasMensualView(APIView):
    """Totales de ventas de cada mes del año."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        try:
            year = int(request.query_params.get("year") or timezone.now().astimezone(TZ).year)
        except (ValueError, TypeError):
            year = timezone.now().astimezone(TZ).year
        tipo = _filtro_tipo(request)

        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        header = ["Mes", "N ventas", "Total S/"]
        rows = []
        gran_total = 0.0
        gran_n = 0
        for m in range(1, 13):
            qs = Venta.objects.filter(
                tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
                fecha_hora__year=year, fecha_hora__month=m,
            ).only("productos_json", "total", "fecha_hora")
            lista = list(qs)
            if tipo == "todos":
                tot = round(sum(calcular_total_venta(v) for v in lista), 2)
                n = len(lista)
            else:
                tot = 0.0
                n = 0
                for v in lista:
                    monto, n_items = _monto_items_tipo(v.productos_json, tipo)
                    if n_items > 0:
                        tot += monto
                        n += 1
                tot = round(tot, 2)
            gran_total += tot
            gran_n += n
            rows.append([meses[m - 1], n, tot])
        rows.append(["TOTAL", gran_n, round(gran_total, 2)])
        suf = _sufijo_filtros(tipo)
        return _csv_response(header, rows, f"ventas_mensual_{year}{suf}.csv")


class ExportGananciasView(APIView):
    """Ganancias de un mes. ?month=1-12&year=2026[&detalle=venta|producto][&tipo=][&metodo_pago=]."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from apps.ganancias.services import ganancia_por_item, get_nombre_producto
        from apps.venta.models import Venta
        from apps.venta.utils import _parse_productos_json

        tienda = request.user.tienda
        detalle = (request.query_params.get("detalle") or "venta").lower()
        if detalle not in ("venta", "producto"):
            detalle = "venta"
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)
        metodo = _filtro_metodo(request)

        qs = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        ).exclude(nota_credito__isnull=False)
        if metodo:
            qs = qs.filter(metodo_pago__iexact=metodo)
        ventas = qs.select_related("comprobante").order_by("fecha_hora")

        suf = f"{year}-{month:02d}{_sufijo_filtros(tipo, metodo)}"
        if detalle == "producto":
            header = ["Fecha", "Comprobante", "Producto", "Tipo", "Cant", "P. venta", "P. compra",
                      "Venta S/", "Costo S/", "Ganancia S/", "Margen %"]
            rows = []
            for v in ventas:
                comp = getattr(v, "comprobante", None)
                num = f"{comp.serie}-{comp.correlativo}" if comp and comp.serie else ""
                fh = v.fecha_hora.astimezone(TZ).date().isoformat()
                for item in _parse_productos_json(v.productos_json):
                    if not isinstance(item, dict):
                        continue
                    if not _quiere_tipo(item, tipo):
                        continue
                    g = ganancia_por_item(item)
                    if g is None or not g.get("calculable"):
                        continue
                    rows.append([fh, num, get_nombre_producto(item), _tipo_item(item), g["cantidad"],
                                 g["precio_venta"], g["precio_compra"],
                                 g["venta"], g["costo"], g["ganancia"], g["margen"]])
            return _csv_response(header, rows, f"ganancias_productos_{suf}.csv")

        header = ["Fecha", "Comprobante", "Cliente", "Venta S/", "Costo S/", "Ganancia S/", "Margen %"]
        rows = []
        tv = tc = tg = 0.0
        for v in ventas:
            r = _ganancia_venta_tipo(v.productos_json, tipo)
            if tipo != "todos" and r["items_ok"] == 0:
                continue
            tv += r["total_venta"]
            tc += r["total_costo"]
            tg += r["ganancia"]
            comp = getattr(v, "comprobante", None)
            num = f"{comp.serie}-{comp.correlativo}" if comp and comp.serie else ""
            fh = v.fecha_hora.astimezone(TZ).date().isoformat()
            rows.append([fh, num, v.nombre_cliente or "Cliente general",
                         r["total_venta"], r["total_costo"], r["ganancia"], r["margen"]])
        margen_total = round((tg / tv) * 100, 2) if tv > 0 else 0.0
        rows.append(["TOTAL", "", "", round(tv, 2), round(tc, 2), round(tg, 2), margen_total])
        return _csv_response(header, rows, f"ganancias_{suf}.csv")


class ExportTopProductosView(APIView):
    """Productos más vendidos del mes, con Tipo (Accesorio/Celular). ?month=1-12&year=."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from collections import Counter, defaultdict

        from apps.ganancias.services import get_nombre_producto
        from apps.venta.models import Venta
        from apps.venta.utils import _get_cantidad_safe, _get_precio_unitario_safe, _parse_productos_json

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)

        ventas = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        ).only("productos_json")

        cant = Counter()
        totales = defaultdict(float)
        tipos = {}
        meta = {}
        for v in ventas:
            for item in _parse_productos_json(v.productos_json):
                if not isinstance(item, dict):
                    continue
                if not _quiere_tipo(item, tipo):
                    continue
                nombre = get_nombre_producto(item)
                cantidad = _get_cantidad_safe(item)
                if cantidad is None:
                    continue
                cant[nombre] += cantidad
                precio = _get_precio_unitario_safe(item, cantidad)
                totales[nombre] += round(precio * cantidad, 2)
                tipos.setdefault(nombre, set()).add(_tipo_item(item))
                if nombre not in meta:
                    meta[nombre] = {"sku": item.get("sku") or "Sin SKU",
                                    "categoria": item.get("categoria_nombre") or ""}

        header = ["Pos", "Producto", "Tipo", "Categoria", "SKU", "Cantidad", "Total S/"]
        rows = []
        for i, (nombre, c) in enumerate(sorted(cant.items(), key=lambda x: x[1], reverse=True), start=1):
            tipo_row = "Celular" if "Celular" in tipos.get(nombre, set()) else "Accesorio"
            rows.append([i, nombre, tipo_row, meta[nombre]["categoria"], meta[nombre]["sku"],
                         c, round(totales.get(nombre, 0.0), 2)])
        return _csv_response(header, rows, f"top_productos_{year}-{month:02d}{_sufijo_filtros(tipo)}.csv")


class ExportTopCategoriasView(APIView):
    """Categorías con más ingresos del mes. ?month=1-12&year=."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from collections import defaultdict

        from apps.venta.models import Venta
        from apps.venta.utils import _get_cantidad_safe, _get_precio_unitario_safe, _parse_productos_json

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)

        ventas = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        ).only("productos_json")

        agrupado = defaultdict(lambda: {"unidades": 0, "ingreso": 0.0, "nombre": None})
        for v in ventas:
            for item in _parse_productos_json(v.productos_json):
                if not isinstance(item, dict):
                    continue
                if not _quiere_tipo(item, tipo):
                    continue
                cat_id = item.get("categoria_id")
                cat_nombre = item.get("categoria_nombre") or "Sin categoría"
                key = cat_id if cat_id is not None else str(cat_nombre).strip()
                cantidad = _get_cantidad_safe(item)
                if cantidad is None:
                    continue
                precio = _get_precio_unitario_safe(item, cantidad)
                agrupado[key]["unidades"] += cantidad
                agrupado[key]["ingreso"] += round(precio * cantidad, 2)
                if agrupado[key]["nombre"] is None:
                    agrupado[key]["nombre"] = cat_nombre

        header = ["Pos", "Categoria", "Unidades", "Ingreso S/"]
        rows = []
        for i, (_, c) in enumerate(sorted(agrupado.items(), key=lambda x: x[1]["ingreso"], reverse=True), start=1):
            rows.append([i, c["nombre"] or "Sin categoría", c["unidades"], round(c["ingreso"], 2)])
        return _csv_response(header, rows, f"top_categorias_{year}-{month:02d}{_sufijo_filtros(tipo)}.csv")


class ExportMetodosPagoView(APIView):
    """Ventas por método de pago del mes. ?month=1-12&year=[&tipo=]."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from collections import defaultdict

        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)

        ventas = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        ).only("metodo_pago", "productos_json", "total")

        agrupado = defaultdict(lambda: {"n": 0, "total": 0.0})
        for v in ventas:
            if tipo == "todos":
                monto = float(calcular_total_venta(v))
            else:
                monto, n_items = _monto_items_tipo(v.productos_json, tipo)
                if n_items == 0:
                    continue
            key = v.metodo_pago or "No especificado"
            agrupado[key]["n"] += 1
            agrupado[key]["total"] += monto

        gran_total = sum(i["total"] for i in agrupado.values())
        header = ["Metodo pago", "N ventas", "Total S/", "% del total"]
        rows = []
        for metodo, info in sorted(agrupado.items(), key=lambda x: x[1]["total"], reverse=True):
            pct = round((info["total"] / gran_total) * 100, 2) if gran_total > 0 else 0.0
            rows.append([metodo, info["n"], round(info["total"], 2), pct])
        rows.append(["TOTAL", sum(i["n"] for i in agrupado.values()), round(gran_total, 2), 100.0 if gran_total > 0 else 0.0])
        return _csv_response(header, rows, f"metodos_pago_{year}-{month:02d}{_sufijo_filtros(tipo)}.csv")


class ExportClientesView(APIView):
    """Clientes que compraron en el mes: compras, total y condición. ?month=1-12&year=."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        metodo = _filtro_metodo(request)

        qs = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        )
        if metodo:
            qs = qs.filter(metodo_pago__iexact=metodo)
        ventas = qs.order_by("fecha_hora")

        por_cliente = {}
        for v in ventas:
            doc = (v.numero_documento_cliente or "").strip()
            key = doc or f"__sin_doc__{(v.nombre_cliente or '').strip().lower()}"
            fh = v.fecha_hora.astimezone(TZ)
            c = por_cliente.get(key)
            if c is None:
                por_cliente[key] = c = {"doc": doc, "nombre": v.nombre_cliente or "Cliente general",
                                        "n": 0, "total": 0.0, "primera": fh, "ultima": fh}
            c["n"] += 1
            c["total"] += float(calcular_total_venta(v))
            c["primera"] = min(c["primera"], fh)
            c["ultima"] = max(c["ultima"], fh)
            if v.nombre_cliente:
                c["nombre"] = v.nombre_cliente

        header = ["Doc", "Cliente", "Compras", "Total S/", "Primera compra", "Ultima compra", "Condicion"]
        rows = []
        for c in sorted(por_cliente.values(), key=lambda x: x["total"], reverse=True):
            if c["doc"]:
                previo = Venta.objects.filter(
                    tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
                    numero_documento_cliente=c["doc"], fecha_hora__lt=inicio,
                ).exists()
                condicion = "Recurrente" if previo else "Nuevo"
            else:
                condicion = "Sin documento"
            rows.append([c["doc"] or "-", c["nombre"], c["n"], round(c["total"], 2),
                         c["primera"].date().isoformat(), c["ultima"].date().isoformat(), condicion])
        suf = _sufijo_filtros("todos", metodo)
        return _csv_response(header, rows, f"clientes_{year}-{month:02d}{suf}.csv")


class ExportAnuladasView(APIView):
    """Ventas anuladas del mes. ?month=1-12&year=[&tipo=][&metodo_pago=]."""

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        tipo = _filtro_tipo(request)
        metodo = _filtro_metodo(request)

        qs = Venta.objects.filter(
            tienda=tienda, estado__in=["ANULADA", "anulada", "Anulada"],
            fecha_hora__gte=inicio, fecha_hora__lte=fin,
        )
        if metodo:
            qs = qs.filter(metodo_pago__iexact=metodo)
        ventas = qs.select_related("comprobante", "usuario").order_by("fecha_hora")

        header = ["Fecha", "Comprobante", "Cliente", "Metodo pago", "Total S/", "Vendedor", "Estado"]
        rows = []
        total = 0.0
        for v in ventas:
            comp = getattr(v, "comprobante", None)
            num = f"{comp.serie}-{comp.correlativo}" if comp and comp.serie else (v.tipo_comprobante or "")
            if tipo == "todos":
                monto = round(float(calcular_total_venta(v)), 2)
            else:
                monto, n_items = _monto_items_tipo(v.productos_json, tipo)
                if n_items == 0:
                    continue
            total += monto
            usuario = getattr(getattr(v, "usuario", None), "username", "") or ""
            rows.append([v.fecha_hora.astimezone(TZ).date().isoformat(), num,
                         v.nombre_cliente or "Cliente general", v.metodo_pago or "",
                         monto, usuario, v.estado or ""])
        rows.append(["TOTAL", "", "", "", round(total, 2), "", ""])
        suf = _sufijo_filtros(tipo, metodo)
        return _csv_response(header, rows, f"anuladas_{year}-{month:02d}{suf}.csv")


class ExportStockBajoView(APIView):
    """Inventario con stock en mínimo o menos (stock actual). Tipo: Accesorio/Repuesto."""

    permission_classes = [IsAuthenticated, PuedeExportarOBackup]

    def get(self, request):
        from django.db.models import F

        from apps.inventario.models import Inventario

        tienda = request.user.tienda
        hoy = timezone.now().astimezone(TZ).date().isoformat()
        grupo = (request.query_params.get("grupo") or "todos").lower()
        if grupo not in ("todos", "accesorios", "repuestos"):
            grupo = "todos"

        qs = Inventario.objects.filter(tienda=tienda, activo=True, cantidad__lte=F("stock_minimo")
                                       ).select_related("producto", "producto__categoria",
                                                        "repuesto", "repuesto__categoria", "proveedor"
                                                        ).order_by("cantidad")

        header = ["Producto", "Tipo", "SKU", "Categoria", "Stock", "Stock min", "Faltante",
                  "Costo", "Valorizado", "Ubicacion", "Proveedor"]
        rows = []
        for inv in qs:
            if inv.repuesto is not None:
                nombre, tipo, sku = inv.repuesto.nombre, "Repuesto", inv.repuesto.ubicacion or ""
                cat = inv.repuesto.categoria.nombre if inv.repuesto.categoria else ""
            else:
                p = inv.producto
                nombre = p.nombre if p else ""
                tipo = "Repuesto" if (p and getattr(getattr(p, "categoria", None), "tipo", "") == "REPUESTO") else "Accesorio"
                sku = p.sku if p else ""
                cat = p.categoria.nombre if p and p.categoria else ""
            if grupo == "accesorios" and tipo != "Accesorio":
                continue
            if grupo == "repuestos" and tipo != "Repuesto":
                continue
            costo = float(inv.costo or 0)
            rows.append([nombre, tipo, sku, cat, inv.cantidad, inv.stock_minimo,
                         max(0, (inv.stock_minimo or 0) - (inv.cantidad or 0)),
                         costo, round(costo * (inv.cantidad or 0), 2), inv.ubicacion or "",
                         inv.proveedor.nombre if inv.proveedor else ""])
        suf = "" if grupo == "todos" else f"_{grupo}"
        return _csv_response(header, rows, f"stock_bajo_{hoy}{suf}.csv")


class ResumenAnualView(APIView):
    """JSON para las tarjetas de destacados: total del año, mejor mes y mejor día.

    GET /api/reports/resumen-anual/?year=2026
    """

    permission_classes = [IsAuthenticated, PuedeExportarDatos]

    def get(self, request):
        from collections import defaultdict

        from apps.venta.models import Venta
        from apps.venta.utils import calcular_total_venta

        tienda = request.user.tienda
        try:
            year = int(request.query_params.get("year") or timezone.now().astimezone(TZ).year)
        except (ValueError, TypeError):
            year = timezone.now().astimezone(TZ).year

        ventas = Venta.objects.filter(
            tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS,
            fecha_hora__year=year,
        ).only("productos_json", "total", "fecha_hora")

        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        por_mes = {m: {"n": 0, "total": 0.0} for m in range(1, 13)}
        por_dia = defaultdict(lambda: {"n": 0, "total": 0.0})
        gran_total = 0.0
        gran_n = 0
        for v in ventas:
            monto = round(float(calcular_total_venta(v)), 2)
            fh = v.fecha_hora.astimezone(TZ)
            por_mes[fh.month]["n"] += 1
            por_mes[fh.month]["total"] += monto
            por_dia[fh.date().isoformat()]["n"] += 1
            por_dia[fh.date().isoformat()]["total"] += monto
            gran_total += monto
            gran_n += 1

        mejor_m = max(range(1, 13), key=lambda m: por_mes[m]["total"])
        mejor_d = max(por_dia.items(), key=lambda kv: kv[1]["total"]) if por_dia else (None, {"n": 0, "total": 0.0})

        return Response(
            {
                "year": year,
                "total_anual": round(gran_total, 2),
                "n_ventas": gran_n,
                "mejor_mes": {
                    "month": mejor_m,
                    "nombre": meses[mejor_m - 1],
                    "total": round(por_mes[mejor_m]["total"], 2),
                    "n_ventas": por_mes[mejor_m]["n"],
                },
                "mejor_dia": {
                    "fecha": mejor_d[0],
                    "total": round(mejor_d[1]["total"], 2),
                    "n_ventas": mejor_d[1]["n"],
                },
            },
            status=status.HTTP_200_OK,
        )


def _nombre_xml_seguro(serie, correlativo, sufijo=""):
    base = f"{serie or 'SN'}-{correlativo or 'SN'}{sufijo}"
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(base)) + ".xml"


def _descargar_xml(url, timeout=15):
    """Descarga el contenido del XML desde su URL. Retorna bytes o None."""
    if not url:
        return None
    try:
        import requests

        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        pass
    return None


class ExportComprobantesZipView(APIView):
    """Respaldo mensual de comprobantes para SUNAT: ZIP con XML + índice CSV.

    ?month=1-12&year= — ordenados por fecha, en carpetas BOLETA/FACTURA/NOTA_CREDITO.
    NO descarga PDFs: solo archivos XML y un índice CSV con las urls
    (xml_url, pdf_url, cdr_url, ticket_url) y el codigo_hash.
    """

    permission_classes = [IsAuthenticated, PuedeHacerBackup]

    def get(self, request):
        import csv as csv_mod
        import zipfile
        from io import BytesIO, StringIO

        from apps.comprobante.models import ComprobanteElectronico, NotaCreditoDB

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        etiqueta = f"{year}-{month:02d}"

        comprobantes = ComprobanteElectronico.objects.filter(
            venta__tienda=tienda, fecha_emision__gte=inicio, fecha_emision__lte=fin,
        ).order_by("fecha_emision", "serie", "correlativo")
        notas = NotaCreditoDB.objects.filter(
            venta__tienda=tienda, fecha_emision__gte=inicio, fecha_emision__lte=fin,
        ).order_by("fecha_emision", "serie", "correlativo")

        buf = BytesIO()
        indice = StringIO()
        indice.write("﻿")
        w = csv_mod.writer(indice)
        w.writerow(["Tipo", "Serie", "Correlativo", "Fecha emision", "Cliente", "Doc cliente",
                    "Total", "Moneda", "Estado SUNAT", "XML en zip", "xml_url",
                    "pdf_url", "cdr_url", "ticket_url", "codigo_hash"])
        n_xml = 0
        n_total = 0

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in comprobantes:
                tipo = (c.tipo_comprobante or "").upper()
                carpeta = "FACTURA" if "FACTURA" in tipo or tipo in ("01", "F") else "BOLETA"
                nombre = _nombre_xml_seguro(c.serie, c.correlativo)
                contenido = None
                if c.xml_firmado:
                    contenido = c.xml_firmado.encode("utf-8") if isinstance(c.xml_firmado, str) else bytes(c.xml_firmado)
                if contenido is None:
                    contenido = _descargar_xml(c.xml_url)
                ruta = f"comprobantes_{etiqueta}/{carpeta}/{nombre}"
                if contenido:
                    zf.writestr(ruta, contenido)
                    n_xml += 1
                    en_zip = "SI"
                else:
                    en_zip = "NO"
                n_total += 1
                fh = c.fecha_emision.astimezone(TZ)
                w.writerow([carpeta, c.serie or "", c.correlativo or "", fh.isoformat(),
                            c.nombre_cliente or "", c.numero_documento_cliente or "",
                            float(c.total or 0), c.moneda or "",
                            c.estado_sunat or "", en_zip, c.xml_url or "",
                            c.pdf_url or "", c.cdr_url or "", c.ticket_url or "",
                            c.codigo_hash or ""])

            for nc in notas:
                nombre = _nombre_xml_seguro(nc.serie, nc.correlativo, sufijo="_NC")
                contenido = _descargar_xml(nc.xml_url)
                ruta = f"comprobantes_{etiqueta}/NOTA_CREDITO/{nombre}"
                if contenido:
                    zf.writestr(ruta, contenido)
                    n_xml += 1
                    en_zip = "SI"
                else:
                    en_zip = "NO"
                n_total += 1
                fh = nc.fecha_emision.astimezone(TZ)
                venta = getattr(nc, "venta", None)
                cliente = getattr(venta, "nombre_cliente", "") or ""
                doc = getattr(venta, "numero_documento_cliente", "") or ""
                w.writerow(["NOTA_CREDITO", nc.serie or "", nc.correlativo or "", fh.isoformat(),
                            cliente, doc, float(nc.total or 0), nc.moneda or "",
                            nc.estado_sunat or "", en_zip, nc.xml_url or "",
                            nc.pdf_url or "", nc.cdr_url or "", "", ""])

            zf.writestr(f"comprobantes_{etiqueta}/indice_comprobantes_{etiqueta}.csv", indice.getvalue().encode("utf-8"))

        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="comprobantes_{etiqueta}.zip"'
        resp["X-Backup-Total"] = str(n_total)
        resp["X-Backup-Xml"] = str(n_xml)
        return resp


class ExportComprasZipView(APIView):
    """Respaldo mensual de comprobantes de COMPRA: ZIP con XML + índice CSV.

    ?month=1-12&year= — ordenados por fecha, en carpetas FACTURA/BOLETA/NOTA_CREDITO.
    Solo XML (comprobante del proveedor + constancia SUNAT) y un índice CSV
    con las urls (xml_comprobante, xml_constancia, pdf_url). No descarga PDFs.
    """

    permission_classes = [IsAuthenticated, PuedeHacerBackup]

    def get(self, request):
        import csv as csv_mod
        import zipfile
        from io import BytesIO, StringIO

        from apps.compras.models import ComprobanteCompra

        tienda = request.user.tienda
        rango, error = _resolver_mes(request)
        if error is not None:
            return error
        inicio, fin, month, year = rango
        etiqueta = f"{year}-{month:02d}"

        compras = ComprobanteCompra.objects.filter(
            tienda=tienda, date_created__gte=inicio, date_created__lte=fin,
        ).select_related("proveedor").order_by("date_created", "serie", "correlativo")

        buf = BytesIO()
        indice = StringIO()
        indice.write("﻿")
        w = csv_mod.writer(indice)
        w.writerow(["Tipo", "Serie", "Correlativo", "Fecha registro", "Proveedor", "RUC proveedor",
                    "Total", "Estado SUNAT", "XML comprobante en zip", "XML constancia en zip",
                    "xml_comprobante_url", "xml_constancia_url", "pdf_url"])
        n_xml = 0
        n_total = 0

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in compras:
                tipo = (c.tipo_comprobante or "").strip()
                carpeta = {"01": "FACTURA", "03": "BOLETA", "07": "NOTA_CREDITO"}.get(tipo, "OTROS")
                base = _nombre_xml_seguro(c.serie, c.correlativo)[:-4]
                prov = c.proveedor.nombre if c.proveedor else ""
                fecha = c.date_created.astimezone(TZ).date().isoformat() if c.date_created else ""

                en_zip_comp = "NO"
                contenido = _descargar_xml(c.xml_comprobante)
                if contenido:
                    zf.writestr(f"compras_{etiqueta}/{carpeta}/{base}.xml", contenido)
                    n_xml += 1
                    en_zip_comp = "SI"

                en_zip_const = "NO"
                contenido = _descargar_xml(c.xml_constancia)
                if contenido:
                    zf.writestr(f"compras_{etiqueta}/{carpeta}/{base}_constancia.xml", contenido)
                    n_xml += 1
                    en_zip_const = "SI"

                n_total += 1
                w.writerow([carpeta, c.serie or "", c.correlativo or "", fecha,
                            prov, c.ruc_proveedor or "", float(c.total or 0),
                            f"{c.estado_codigo or ''} {c.estado_descripcion or ''}".strip(),
                            en_zip_comp, en_zip_const,
                            c.xml_comprobante or "", c.xml_constancia or "", c.pdf_url or ""])

            zf.writestr(f"compras_{etiqueta}/indice_compras_{etiqueta}.csv", indice.getvalue().encode("utf-8"))

        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="compras_{etiqueta}.zip"'
        resp["X-Backup-Total"] = str(n_total)
        resp["X-Backup-Xml"] = str(n_xml)
        return resp


class ExportClientesTablaView(APIView):
    """Tabla completa de clientes de la tienda (sin filtro de periodo)."""

    permission_classes = [IsAuthenticated, PuedeHacerBackup]

    def get(self, request):
        from apps.cliente.models import Cliente

        tienda = request.user.tienda
        hoy = timezone.now().astimezone(TZ).date().isoformat()

        qs = Cliente.objects.filter(tienda=tienda).order_by("fullname")

        header = ["Doc", "Nombre completo", "Nombres", "Apellidos", "Departamento",
                  "Provincia", "Distrito", "Direccion", "Telefono", "Email", "Fecha registro"]
        rows = []
        for c in qs:
            fecha = c.date_created.astimezone(TZ).date().isoformat() if c.date_created else ""
            rows.append([c.document or "", c.fullname or "", c.firstname or "", c.lastname or "",
                         c.department or "", c.province or "", c.district or "",
                         c.address or "", c.phone or "", c.email or "", fecha])
        return _csv_response(header, rows, f"clientes_tabla_{hoy}.csv")
