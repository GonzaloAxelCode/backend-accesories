from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.venta.models import Venta
from apps.venta.utils import _get_cantidad_safe, _parse_productos_json

from .services import ganancia_por_item, ganancia_por_venta, get_nombre_producto

TZ = ZoneInfo("America/Lima")
ESTADOS_VALIDOS = ["ACEPTADO", "aceptado", "Aceptado"]


def _base_qs(tienda):
    return Venta.objects.filter(
        tienda=tienda, activo=True, estado__in=ESTADOS_VALIDOS
    )


def _parse_fecha(valor):
    """Acepta 'YYYY-MM-DD' o [dia, mes, año]. Retorna date o None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (list, tuple)) and len(valor) == 3:
        try:
            d, m, y = int(valor[0]), int(valor[1]), int(valor[2])
            return datetime(y, m, d).date()
        except Exception:
            return None
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def _resolver_rango(data):
    """Resuelve (inicio, fin) tz-aware desde fecha_inicio/fecha_fin o from_date/to_date."""
    f_ini = data.get("fecha_inicio", data.get("from_date"))
    f_fin = data.get("fecha_fin", data.get("to_date"))
    d_ini = _parse_fecha(f_ini)
    d_fin = _parse_fecha(f_fin)
    if d_ini is None or d_fin is None:
        return None, None, "Se requiere fecha_inicio y fecha_fin (YYYY-MM-DD o [dia, mes, año])"
    if d_ini > d_fin:
        return None, None, "fecha_inicio no puede ser mayor que fecha_fin"
    inicio = datetime(d_ini.year, d_ini.month, d_ini.day, 0, 0, 0, tzinfo=TZ)
    fin = datetime(d_fin.year, d_fin.month, d_fin.day, 23, 59, 59, tzinfo=TZ)
    return inicio, fin, None


class GananciaRangoView(APIView):
    """1. Ganancias netas en soles: día, últimos 7 días y mes.

    GET /api/ganancias/rango/ -> valores del día actual (America/Lima).
    POST /api/ganancias/rango/ con body JSON opcional:
        {
          "fecha": "2026-09-16",   # también acepta "fecha_dia" / "fecha_hoy" o [dia, mes, año]
          "month": 8,              # 0-11, misma convención que reports/monthly/
          "year": 2026
        }
    - "fecha": día puntual para ganancia_hoy. Si no se envía, usa hoy.
    - semana (ganancia_7dias): siempre últimos 7 días respecto a hoy, no se envía.
    - "month"/"year": mes puntual para ganancia_mes. Si no se envían, usa mes actual.
    Solo retorna 3 propiedades.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self._responder(request)

    def post(self, request):
        return self._responder(request)

    def _responder(self, request):
        from calendar import monthrange
        from datetime import timedelta

        hoy_real = timezone.now().astimezone(TZ).date()
        es_post = request.method == "POST"
        data = request.data if es_post and isinstance(request.data, dict) else {}

        # --- 1. Día puntual (ganancia_hoy): fecha enviada o hoy ---
        fecha_raw = data.get("fecha", data.get("fecha_dia", data.get("fecha_hoy")))
        if fecha_raw is None or fecha_raw == "":
            fecha_dia = hoy_real
        else:
            fecha_dia = _parse_fecha(fecha_raw)
            if fecha_dia is None:
                return Response(
                    {"error": "fecha inválida. Use YYYY-MM-DD o [dia, mes, año]"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        inicio_dia = datetime(fecha_dia.year, fecha_dia.month, fecha_dia.day, 0, 0, 0, tzinfo=TZ)
        fin_dia = datetime(fecha_dia.year, fecha_dia.month, fecha_dia.day, 23, 59, 59, tzinfo=TZ)

        # --- 2. Semana: siempre últimos 7 días respecto a hoy (no se envía) ---
        dia_7 = hoy_real - timedelta(days=6)  # últimos 7 días incluyendo hoy
        inicio_7 = datetime(dia_7.year, dia_7.month, dia_7.day, 0, 0, 0, tzinfo=TZ)
        fin_7 = datetime(hoy_real.year, hoy_real.month, hoy_real.day, 23, 59, 59, tzinfo=TZ)

        # --- 3. Mes puntual (ganancia_mes): month/year enviados o mes actual ---
        if data.get("month") is not None or data.get("year") is not None:
            try:
                month = int(data.get("month"))
                year = int(data.get("year"))
            except (ValueError, TypeError):
                return Response(
                    {"error": "month y year deben ser números enteros"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if month < 0 or month > 11:
                return Response(
                    {"error": "El mes debe estar entre 0 y 11"}, status=status.HTTP_400_BAD_REQUEST
                )
            if year < 2000:
                return Response(
                    {"error": "El año debe ser mayor a 2000"}, status=status.HTTP_400_BAD_REQUEST
                )
            mes, anio = month + 1, year
        else:
            mes, anio = hoy_real.month, hoy_real.year
        inicio_mes = datetime(anio, mes, 1, 0, 0, 0, tzinfo=TZ)
        ultimo_dia = monthrange(anio, mes)[1]
        fin_mes = datetime(anio, mes, ultimo_dia, 23, 59, 59, tzinfo=TZ)

        ventas = (
            _base_qs(request.user.tienda)
            .filter(
                fecha_hora__gte=min(inicio_dia, inicio_7, inicio_mes),
                fecha_hora__lte=max(fin_dia, fin_7, fin_mes),
            )
            .only("fecha_hora", "productos_json")
        )

        g_hoy = 0.0
        g_7 = 0.0
        g_mes = 0.0
        for v in ventas:
            g = ganancia_por_venta(v.productos_json)["ganancia"]
            flocal = v.fecha_hora.astimezone(TZ)
            if inicio_mes <= flocal <= fin_mes:
                g_mes += g
            if inicio_7 <= flocal <= fin_7:
                g_7 += g
            if inicio_dia <= flocal <= fin_dia:
                g_hoy += g

        return Response(
            {
                "ganancia_hoy": round(g_hoy, 2),
                "ganancia_7dias": round(g_7, 2),
                "ganancia_mes": round(g_mes, 2),
            },
            status=status.HTTP_200_OK,
        )


def _get_descuento_safe(item):
    """Extrae descuento total de la línea como float >= 0."""
    raw = item.get("descuento", 0)
    if raw in (None, ""):
        return 0.0
    try:
        val = float(raw)
    except (ValueError, TypeError):
        try:
            val = float(str(raw).replace(",", "."))
        except Exception:
            return 0.0
    if val < 0:
        return 0.0
    return val


def _get_imagen_absoluta(item, request=None):
    """Retorna URL de imagen completa (absoluta si hay request)."""
    raw = item.get("imagen") or item.get("img_url") or item.get("producto_imagen")
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if request is not None and raw.startswith("/"):
        try:
            return request.build_absolute_uri(raw)
        except Exception:
            return raw
    return raw


def _get_categoria_snapshot(item):
    """Extrae categoria del snapshot: id, nombre, color."""
    cat_data = item.get("categoria_data") if isinstance(item.get("categoria_data"), dict) else {}
    cat_id = item.get("categoria_id")
    if cat_id is None:
        cat_id = cat_data.get("categoria_id")
    nombre = item.get("categoria_nombre") or cat_data.get("nombre") or "Sin categoría"
    color = item.get("categoria_color") or cat_data.get("color")
    return cat_id, str(nombre).strip() or "Sin categoría", color


def _acumular_productos(ventas_qs, request=None):
    """Agrupa por producto: nombre, imagen, total facturado, ganancia neta, descuentos, categoria, cantidad."""
    grupo = {}
    items_sin_costo = 0
    for venta in ventas_qs:
        for item in _parse_productos_json(venta.productos_json):
            if not isinstance(item, dict):
                continue
            cantidad = _get_cantidad_safe(item)
            if cantidad is None:
                continue
            r = ganancia_por_item(item)
            if r is None or not r["calculable"]:
                items_sin_costo += 1
                continue
            nombre = get_nombre_producto(item)
            pid = item.get("producto_id")
            key = pid if pid is not None else nombre
            imagen = _get_imagen_absoluta(item, request)
            descuento = _get_descuento_safe(item)
            cat_id, cat_nombre, cat_color = _get_categoria_snapshot(item)
            if key not in grupo:
                grupo[key] = {
                    "producto_id": pid,
                    "nombre": nombre,
                    "imagen": imagen,
                    "categoria": {
                        "categoria_id": cat_id,
                        "nombre": cat_nombre,
                        "color": cat_color,
                    },
                    "cantidad_vendida": 0,
                    "total_facturado": 0.0,
                    "costo_total": 0.0,
                    "descuentos_totales": 0.0,
                }
            g = grupo[key]
            g["cantidad_vendida"] += cantidad
            g["total_facturado"] += r["venta"]
            g["costo_total"] += r["costo"]
            g["descuentos_totales"] += descuento
            # refrescar nombre/imagen/categoria si faltaban
            if g["nombre"] in (None, "", "Sin nombre"):
                g["nombre"] = nombre
            if not g["imagen"] and imagen:
                g["imagen"] = imagen
            if g["categoria"].get("nombre") in (None, "", "Sin categoría") and cat_nombre != "Sin categoría":
                g["categoria"] = {
                    "categoria_id": cat_id,
                    "nombre": cat_nombre,
                    "color": cat_color,
                }
            if g["categoria"].get("categoria_id") is None and cat_id is not None:
                g["categoria"]["categoria_id"] = cat_id
            if not g["categoria"].get("color") and cat_color:
                g["categoria"]["color"] = cat_color
    for g in grupo.values():
        g["total_facturado"] = round(g["total_facturado"], 2)
        g["costo_total"] = round(g["costo_total"], 2)
        g["descuentos_totales"] = round(g["descuentos_totales"], 2)
        g["ganancia_neta"] = round(g["total_facturado"] - g["costo_total"], 2)
        # aliases compatibilidad
        g["venta_total"] = g["total_facturado"]
        g["ganancia_soles"] = g["ganancia_neta"]
        g["unidades"] = g["cantidad_vendida"]
    return grupo, items_sin_costo


class TopProductosMesView(APIView):
    """3. Top 10 productos que más ganancia neta dejaron en un mes.

    POST { month: 0-11, year } (misma convención que reports/monthly/).
    Ordena por ganancia_neta desc.
    Cada producto: nombre, imagen, total_facturado, ganancia_neta,
    descuentos_totales, categoria, cantidad_vendida.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            month = int(request.data.get("month", -1))
            year = int(request.data.get("year", 0))
        except (ValueError, TypeError):
            return Response(
                {"error": "month y year deben ser números enteros"}, status=status.HTTP_400_BAD_REQUEST
            )
        if month < 0 or month > 11:
            return Response({"error": "El mes debe estar entre 0 y 11"}, status=status.HTTP_400_BAD_REQUEST)
        if year < 2000:
            return Response({"error": "El año debe ser mayor a 2000"}, status=status.HTTP_400_BAD_REQUEST)

        mes = month + 1
        ventas = _base_qs(request.user.tienda).filter(
            fecha_hora__year=year, fecha_hora__month=mes
        ).only("productos_json")

        grupo, items_sin_costo = _acumular_productos(ventas, request=request)
        top = sorted(grupo.values(), key=lambda x: x["ganancia_neta"], reverse=True)[:10]
        productos = []
        for i, p in enumerate(top, start=1):
            productos.append(
                {
                    "posicion": i,
                    "producto_id": p["producto_id"],
                    "nombre": p["nombre"],
                    "imagen": p["imagen"],
                    "categoria": p["categoria"],
                    "cantidad_vendida": p["cantidad_vendida"],
                    "total_facturado": p["total_facturado"],
                    "ganancia_neta": p["ganancia_neta"],
                    "descuentos_totales": p["descuentos_totales"],
                }
            )

        ganancia_mes = round(sum(g["ganancia_neta"] for g in grupo.values()), 2)
        return Response(
            {
                "month": month,
                "year": year,
                "ganancia_mes_soles": ganancia_mes,
                "total_productos": len(grupo),
                "items_sin_costo": items_sin_costo,
                "productos": productos,
            },
            status=status.HTTP_200_OK,
        )
