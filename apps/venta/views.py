from collections import Counter
from datetime import timedelta, datetime, time, date
from zoneinfo import ZoneInfo
from decimal import Decimal
from math import ceil
import json

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.utils.timezone import make_aware, now, localtime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.comprobante.models import ComprobanteElectronico
from core.permissions import CanCancelSalePermission, CanMakeSalePermission
from .models import Venta, VentaProducto
from apps.venta.utils import ClienteService, InventarioService, VentaService, ComprobanteService, SunatService
from apps.venta.exceptions import (
    StockInsuficienteError,
    InventarioNoEncontradoError,
    DatosInvalidosError,
    SunatError,
    SunatRechazadoError,
)
from django.contrib.auth import get_user_model
class VentaPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100

User = get_user_model()

class CreateSaleView(APIView):
    permission_classes = [IsAuthenticated, CanMakeSalePermission]

    def post(self, request):
        try:
            data = request.data
            tienda = request.user.tienda
            usuario = request.user
            cliente_data = ClienteService.resolve_cliente(data.get("cliente"), tienda)

            fecha_hora = timezone.now()

            productos_registrados = []
            productos_items_for_sunat = []

            subtotal = Decimal("0.00")
            gravado_total = Decimal("0.00")
            igv_total = Decimal("0.00")
            total = Decimal("0.00")

            with transaction.atomic():
                venta = Venta.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    metodo_pago=data["metodoPago"],
                    tipo_comprobante=data["tipoComprobante"],
                    fecha_hora=fecha_hora,
                    estado="PENDIENTE",
                    tipo_documento_cliente="6" if data["tipoComprobante"] == "Factura" else "1",
                    numero_documento_cliente=cliente_data["numero"],
                    nombre_cliente=(
                        cliente_data["nombre_o_razon_social"]
                        if data["tipoComprobante"] == "Factura"
                        else cliente_data["nombre_completo"]
                    ),
                    email_cliente=data.get("correo_cliente"),
                    telefono_cliente=data.get("telefono_cliente"),
                    direccion_cliente=data.get("direccion_cliente"),
                )

                items_locked = InventarioService.validate_and_lock_stock(data["productos"])

                for item, (inventario, cantidad) in zip(data["productos"], items_locked):
                    calculo = VentaService.calcular_producto(item, inventario, cantidad)

                    VentaService.create_venta_producto(venta, calculo)

                    subtotal += calculo["valor_venta"]
                    gravado_total += calculo["valor_venta"]
                    igv_total += calculo["igv"]
                    total += calculo["precio_unitario"] * cantidad

                    productos_registrados.append(VentaService.build_producto_registrado(calculo))
                    productos_items_for_sunat.append(VentaService.build_item_sunat(calculo))

                InventarioService.deduct_stock(items_locked)

                venta.subtotal = subtotal
                venta.gravado_total = gravado_total
                venta.igv_total = igv_total
                venta.total = total
                venta.productos_json = productos_registrados
                venta.save()

                leyenda = SunatService.generate_leyenda(total)
                serie, correlativo = ComprobanteService.get_siguiente(data["tipoComprobante"], tienda)

                comprobante_data = SunatService.build_comprobante_data(
                    venta, tienda, serie, correlativo,
                    gravado_total, igv_total, subtotal, total,
                    leyenda, productos_items_for_sunat,
                )

                comprobante = ComprobanteElectronico.objects.create(
                    venta=venta,
                    tipo_comprobante=data["tipoComprobante"],
                    serie=serie,
                    correlativo=correlativo,
                    moneda="PEN",
                    gravadas=gravado_total,
                    igv=igv_total,
                    valorVenta=subtotal,
                    sub_total=subtotal + igv_total,
                    total=total,
                    leyenda=leyenda,
                    tipo_documento_cliente=venta.tipo_documento_cliente,
                    numero_documento_cliente=venta.numero_documento_cliente,
                    nombre_cliente=venta.nombre_cliente,
                    estado_sunat="PENDIENTE",
                    items=comprobante_data["items"],
                )

            # SUNAT fuera del atomic
            try:
                response_json = SunatService.send_to_sunat(
                    comprobante_data, data["tipoComprobante"]
                )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            SunatService.process_sunat_response(response_json, comprobante, venta)
            comprobante_json = SunatService.build_comprobante_response(comprobante, response_json)

            venta_json = {
                "id": venta.id,
                "usuario": usuario.id,
                "tienda": tienda.id,
                "metodo_pago": venta.metodo_pago,
                "tipo_comprobante": venta.tipo_comprobante,
                "estado": venta.estado,
                "activo": venta.activo,
                "fecha_hora": venta.fecha_hora.isoformat(),
                "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                "gravado_total": float(gravado_total),
                "igv_total": float(igv_total),
                "total": float(total),
                "productos_json": json.dumps(productos_registrados),
                "productos": productos_registrados,
                "comprobante_data": comprobante_data,
                "comprobante": comprobante_json,
            }

            return Response(venta_json, status=status.HTTP_201_CREATED)

        except StockInsuficienteError as e:
            return Response(
                {"error": "Stock insuficiente", "detalles": e.errores},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InventarioNoEncontradoError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DatosInvalidosError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SunatRechazadoError as e:
            return Response(
                {"error": "SUNAT rechazó el comprobante", "codigo": e.cdr_codigo, "detalle": str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except SunatError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except KeyError as e:
            return Response(
                {"error": f"Falta el campo obligatorio: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ValueError, TypeError) as e:
            return Response(
                {"error": f"Valor inválido: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



class SalesSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_summary(self, tienda_id):
        """Calcula día/semana/mes usando productos_json (precio_unitario ya con descuento)."""
        from apps.venta.utils import calcular_total_venta

        today = localtime(now()).date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        current_year = today.year

        ventas_activas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
        )

        def _sum_productos_json(qs):
            total = 0.0
            for v in qs.only("productos_json", "total"):
                total += calcular_total_venta(v)  # productos_json: sum(precio_unitario * cantidad) con descuento restado
            return round(total, 2)

        today_sales = _sum_productos_json(
            ventas_activas.filter(fecha_hora__date=today)
        )

        this_week_sales = _sum_productos_json(
            ventas_activas.filter(
                fecha_hora__date__gte=start_of_week,
                fecha_hora__date__lte=today,
                fecha_hora__year=current_year,
            )
        )

        this_month_sales = _sum_productos_json(
            ventas_activas.filter(
                fecha_hora__date__gte=start_of_month,
                fecha_hora__date__lte=today,
                fecha_hora__year=current_year,
            )
        )

        return {
            "todaySales": today_sales,
            "thisWeekSales": this_week_sales,
            "thisMonthSales": this_month_sales,
        }

    def post(self, request, *args, **kwargs):
        tienda_id = request.user.tienda_id
        return Response(self._get_summary(tienda_id))

    def get(self, request, *args, **kwargs):
        tienda_id = request.user.tienda_id
        return Response(self._get_summary(tienda_id))


class SalesByDateRangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from_date = request.data.get('from_date')
        to_date = request.data.get('to_date')
        tienda_id = request.user.tienda

        if not from_date or not to_date:
            return Response({"error": "Se debe proporcionar un rango de fechas válido"}, status=status.HTTP_400_BAD_REQUEST)

        tz = timezone.get_current_timezone()

        from_date_obj = make_aware(
            datetime(from_date[0], from_date[1] + 1, from_date[2]),
            timezone=tz
        )

        to_date_obj = make_aware(
            datetime(to_date[0], to_date[1] + 1, to_date[2]),
            timezone=tz
        )

        from_date_obj = from_date_obj.date()
        to_date_obj = to_date_obj.date()
        to_date_obj_exclusive = to_date_obj + timedelta(days=1)

        date_range = []
        current_date = from_date_obj
        while current_date < to_date_obj_exclusive:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        ventas = Venta.objects.filter(
            tienda=tienda_id,
            activo=True,
            fecha_hora__gte=from_date_obj,
            fecha_hora__lt=to_date_obj_exclusive,
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
        )

        daily_sales = {}
        for venta in ventas:
            dia = localtime(venta.fecha_hora).date()
            productos = venta.productos_json
            total_venta = 0.0
            if productos:
                if isinstance(productos, str):
                    try:
                        productos = json.loads(productos)
                    except Exception:
                        productos = []
                if isinstance(productos, list):
                    for item in productos:
                        if not isinstance(item, dict):
                            continue
                        cantidad = item.get("cantidad", 0)
                        try:
                            cantidad = int(cantidad)
                        except (ValueError, TypeError):
                            try:
                                cantidad = int(float(str(cantidad)))
                            except Exception:
                                continue
                        if cantidad <= 0:
                            continue
                        precio_raw = item.get("precio_unitario")
                        if precio_raw is None:
                            base = item.get("precio_venta")
                            if base is None:
                                base = item.get("costo_original")
                            if base is not None:
                                try:
                                    base_f = float(base)
                                except Exception:
                                    try:
                                        base_f = float(str(base).replace(",", "."))
                                    except Exception:
                                        base_f = 0.0
                                disc_raw = item.get("descuento")
                                try:
                                    descuento = float(disc_raw) if disc_raw not in (None, "") else 0.0
                                except Exception:
                                    descuento = 0.0
                                if descuento and cantidad:
                                    precio_raw = base_f - (descuento / cantidad)
                                else:
                                    precio_raw = base_f
                            else:
                                vu = item.get("valor_unitario")
                                if vu is not None:
                                    try:
                                        precio_raw = float(vu) * 1.18
                                    except Exception:
                                        precio_raw = 0
                                elif item.get("valor_venta") is not None and cantidad:
                                    try:
                                        precio_raw = float(item.get("valor_venta")) / cantidad * 1.18
                                    except Exception:
                                        precio_raw = 0
                                else:
                                    precio_raw = 0
                        try:
                            precio = float(precio_raw)
                        except (ValueError, TypeError):
                            try:
                                precio = float(str(precio_raw).replace(",", "."))
                            except Exception:
                                precio = 0.0
                        total_venta += round(precio * cantidad, 2)
            daily_sales[dia] = daily_sales.get(dia, 0.0) + total_venta

        sales_date_range = [
            [f"{date.year}, {date.month - 1}, {date.day}", round(float(daily_sales.get(date, 0)), 2)]
            for date in date_range
        ]

        return Response({"salesDateRangePerDay": sales_date_range}, status=status.HTTP_200_OK)


class TopProductsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.venta.utils import _parse_productos_json, _get_cantidad_safe

        tienda = request.user.tienda
        hoy = datetime.now().date()

        from_date = make_aware(datetime.combine(hoy, time.min))
        to_date = make_aware(datetime.combine(hoy, time.max))

        ventas = Venta.objects.filter(
            tienda=tienda,
            activo=True,
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            fecha_hora__range=(from_date, to_date)
        ).only("productos_json")

        contador = Counter()
        for venta in ventas:
            for item in _parse_productos_json(venta.productos_json):
                if not isinstance(item, dict):
                    continue
                nombre = item.get("producto_nombre") or item.get("nombre") or item.get("descripcion")
                if not nombre:
                    continue
                nombre = str(nombre).strip()
                if not nombre:
                    continue
                cantidad = _get_cantidad_safe(item)
                if cantidad is None:
                    continue
                contador[nombre] += cantidad

        productos_data = [
            {"nombre": nombre, "cantidad_total_vendida": cantidad}
            for nombre, cantidad in contador.items()
        ]

        productos_data.sort(key=lambda x: x["cantidad_total_vendida"], reverse=True)

        return Response({"results": productos_data})


class TopProductsByMonthView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tienda = request.user.tienda
        hoy = datetime.now().date()

        month = request.data.get("month", "")
        if month:
            try:
                partes = month.split("-")
                year = int(partes[0])
                mes = int(partes[1])
            except (ValueError, IndexError):
                return Response(
                    {"error": "Formato de month inválido. Usa 'YYYY-MM' (ej: '2026-06')."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            year = hoy.year
            mes = hoy.month

        from_date = make_aware(datetime(year, mes, 1, 0, 0, 0))
        if mes == 12:
            to_date = make_aware(datetime(year + 1, 1, 1, 0, 0, 0))
        else:
            to_date = make_aware(datetime(year, mes + 1, 1, 0, 0, 0))

        ventas = Venta.objects.filter(
            tienda=tienda,
            activo=True,
            total__gt=0,
            fecha_hora__gte=from_date,
            fecha_hora__lt=to_date,
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
        ).only("productos_json")

        contador = Counter()
        totales = {}
        for venta in ventas:
            productos = venta.productos_json
            if not productos:
                continue
            if isinstance(productos, str):
                try:
                    productos = json.loads(productos)
                except Exception:
                    continue
            if not isinstance(productos, list):
                continue
            for item in productos:
                if not isinstance(item, dict):
                    continue
                nombre = item.get("producto_nombre") or item.get("nombre") or item.get("descripcion")
                if not nombre:
                    continue
                nombre = str(nombre).strip()
                if not nombre:
                    continue
                cant_raw = item.get("cantidad", 0)
                try:
                    cantidad = int(cant_raw)
                except (ValueError, TypeError):
                    try:
                        cantidad = int(float(str(cant_raw)))
                    except Exception:
                        continue
                if cantidad <= 0:
                    continue
                contador[nombre] += cantidad

                precio_raw = item.get("precio_unitario")
                if precio_raw is None:
                    base = item.get("precio_venta")
                    if base is None:
                        base = item.get("costo_original")
                    if base is not None:
                        try:
                            base_f = float(base)
                        except Exception:
                            try:
                                base_f = float(str(base).replace(",", "."))
                            except Exception:
                                base_f = 0.0
                        disc_raw = item.get("descuento")
                        try:
                            descuento = float(disc_raw) if disc_raw not in (None, "") else 0.0
                        except Exception:
                            descuento = 0.0
                        if descuento and cantidad:
                            precio_raw = base_f - (descuento / cantidad)
                        else:
                            precio_raw = base_f
                    else:
                        vu = item.get("valor_unitario")
                        if vu is not None:
                            try:
                                precio_raw = float(vu) * 1.18
                            except Exception:
                                precio_raw = 0
                        elif item.get("valor_venta") is not None and cantidad:
                            try:
                                precio_raw = float(item.get("valor_venta")) / cantidad * 1.18
                            except Exception:
                                precio_raw = 0
                        else:
                            precio_raw = 0

                try:
                    precio = float(precio_raw)
                except (ValueError, TypeError):
                    try:
                        precio = float(str(precio_raw).replace(",", "."))
                    except Exception:
                        precio = 0.0

                total_linea = round(precio * cantidad, 2)
                totales[nombre] = totales.get(nombre, 0.0) + total_linea

        productos_data = [
            {
                "nombre": nombre,
                "cantidad_total_vendida": cantidad,
                "unidades_vendidas": cantidad,
                "total_vendido": round(totales.get(nombre, 0.0), 2),
                "monto_total_vendido": round(totales.get(nombre, 0.0), 2),
            }
            for nombre, cantidad in contador.items()
        ]

        productos_data.sort(key=lambda x: x["cantidad_total_vendida"], reverse=True)

        return Response({
            "year": year,
            "month": mes,
            "results": productos_data,
        })


class SalesByDayMonthView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        tienda_id = request.user.tienda_id
        year = int(request.data.get("year", 0))
        month = int(request.data.get("month", 0))
        day = int(request.data.get("day", 0))
        week = int(request.data.get("week", 0))
        tipo = request.data.get("tipo", "default")

        if not tienda_id:
            return Response({"error": "Se requiere el ID de la tienda."}, status=400)

        ventas_activas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
        )

        today_sales = None
        this_month_sales = None
        this_week_sales = None
        sales_count = None

        def _calcular_total_productos_json(ventas):
            total = 0.0
            for venta in ventas:
                productos = venta.productos_json
                if not productos:
                    continue
                if isinstance(productos, str):
                    try:
                        productos = json.loads(productos)
                    except Exception:
                        continue
                if not isinstance(productos, list):
                    continue
                for item in productos:
                    if not isinstance(item, dict):
                        continue
                    cantidad = item.get("cantidad", 0)
                    try:
                        cantidad = int(cantidad)
                    except (ValueError, TypeError):
                        try:
                            cantidad = int(float(str(cantidad)))
                        except Exception:
                            continue
                    if cantidad <= 0:
                        continue

                    precio_raw = item.get("precio_unitario")
                    if precio_raw is None:
                        base = item.get("precio_venta")
                        if base is None:
                            base = item.get("costo_original")
                        if base is not None:
                            try:
                                base_f = float(base)
                            except Exception:
                                try:
                                    base_f = float(str(base).replace(",", "."))
                                except Exception:
                                    base_f = 0.0
                            disc_raw = item.get("descuento")
                            try:
                                descuento = float(disc_raw) if disc_raw not in (None, "") else 0.0
                            except Exception:
                                descuento = 0.0
                            if descuento and cantidad:
                                precio_raw = base_f - (descuento / cantidad)
                            else:
                                precio_raw = base_f
                        else:
                            vu = item.get("valor_unitario")
                            if vu is not None:
                                try:
                                    precio_raw = float(vu) * 1.18
                                except Exception:
                                    precio_raw = 0
                            elif item.get("valor_venta") is not None and cantidad:
                                try:
                                    precio_raw = float(item.get("valor_venta")) / cantidad * 1.18
                                except Exception:
                                    precio_raw = 0
                            else:
                                precio_raw = 0

                    try:
                        precio = float(precio_raw)
                    except (ValueError, TypeError):
                        try:
                            precio = float(str(precio_raw).replace(",", "."))
                        except Exception:
                            precio = 0.0

                    total += round(precio * cantidad, 2)

            return round(total, 2)

        try:
            if tipo == "day_month_year" and year and month and day:
                selected_date = date(year, month, day)
                tz = timezone.get_current_timezone()
                start_of_day = make_aware(datetime.combine(selected_date, time.min), timezone=tz)
                end_of_day = start_of_day + timedelta(days=1)
                ventas = ventas_activas.filter(
                    fecha_hora__gte=start_of_day,
                    fecha_hora__lt=end_of_day
                )
                sales_count = ventas.count()
                today_sales = _calcular_total_productos_json(ventas)

            elif tipo == "month_year" and year and month:
                start_of_month = date(year, month, 1)
                if month == 12:
                    end_of_month = date(year + 1, 1, 1)
                else:
                    end_of_month = date(year, month + 1, 1)

                tz = timezone.get_current_timezone()
                start_dt = make_aware(datetime.combine(start_of_month, time.min), timezone=tz)
                end_dt = make_aware(datetime.combine(end_of_month, time.min), timezone=tz)

                ventas = ventas_activas.filter(
                    fecha_hora__gte=start_dt,
                    fecha_hora__lt=end_dt
                )
                sales_count = ventas.count()
                this_month_sales = _calcular_total_productos_json(ventas)

            elif tipo == "week_year" and year and week:
                jan4 = date(year, 1, 4)
                start_of_week = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week - 1)
                end_of_week = start_of_week + timedelta(days=7)

                tz = timezone.get_current_timezone()
                start_dt = make_aware(datetime.combine(start_of_week, time.min), timezone=tz)
                end_dt = make_aware(datetime.combine(end_of_week, time.min), timezone=tz)

                ventas = ventas_activas.filter(
                    fecha_hora__gte=start_dt,
                    fecha_hora__lt=end_dt
                )
                sales_count = ventas.count()
                this_week_sales = _calcular_total_productos_json(ventas)

            else:
                return Response({
                    "todaySales": None,
                    "thisMonthSales": None,
                    "thisWeekSales": None,
                    "salesCount": None,
                    "tipo": "default"
                })

        except ValueError:
            return Response({"error": "Fecha inválida."}, status=400)

        return Response({
            "todaySales": today_sales,
            "thisMonthSales": this_month_sales,
            "thisWeekSales": this_week_sales,
            "salesCount": sales_count,
            "tipo": tipo
        })


class SalesDailyTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tienda = request.user.tienda
        tienda_id = request.user.tienda_id if hasattr(request.user, 'tienda_id') else (tienda.id if tienda else None)
        if not tienda_id:
            return Response({"error": "Se requiere el ID de la tienda."}, status=400)

        days = int(request.data.get("days", 20))
        hoy = timezone.localdate()

        desde = hoy - timedelta(days=days - 1)

        from apps.venta.utils import calcular_total_venta

        ventas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            fecha_hora__date__gte=desde,
            fecha_hora__date__lte=hoy,
        ).only("productos_json", "total", "fecha_hora")

        por_dia = {}
        for v in ventas:
            dia = localtime(v.fecha_hora).date().isoformat()
            por_dia[dia] = por_dia.get(dia, 0) + calcular_total_venta(v)

        resultados = []
        current = desde
        while current <= hoy:
            key = current.isoformat()
            resultados.append({
                "fecha": key,
                "total": round(por_dia.get(key, 0), 2),
            })
            current += timedelta(days=1)

        return Response({"results": resultados})






class SearchSalesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        page_number = int(request.data.get('page', 1))
        page_size = int(request.data.get('page_size', 5))
        tienda_id = request.user.tienda
        query = request.data.get('query', {})
        ventas = Venta.objects.filter(tienda_id=tienda_id, total__gt=0)

        from_date = query.get('from_date')
        to_date = query.get('to_date')

        tz = timezone.get_current_timezone()

        from_date_obj = make_aware(
            datetime(year=from_date[0], month=from_date[1] + 1, day=from_date[2], hour=0, minute=0, second=0),
            timezone=tz
        )

        to_date_obj = make_aware(
            datetime(year=to_date[0], month=to_date[1] + 1, day=to_date[2], hour=23, minute=59, second=59),
            timezone=tz
        )

        ventas = ventas.filter(fecha_hora__range=(from_date_obj, to_date_obj), total__gt=0)

        metodo_pago = query.get('metodo_pago')
        tipo_comprobante = query.get('tipo_comprobante')
        nombre_cliente = query.get('nombre_cliente')
        numero_documento_cliente = query.get('numero_documento_cliente')
        numero_comprobante = query.get('numero_comprobante')
        estado_sunat = query.get('estado_sunat')

        if metodo_pago is not "":
            ventas = ventas.filter(metodo_pago__icontains=metodo_pago, total__gt=0)
        if estado_sunat is not "":
            ventas = ventas.filter(comprobante__estado_sunat__icontains=estado_sunat, total__gt=0)
        if tipo_comprobante is not "":
            ventas = ventas.filter(tipo_comprobante__icontains=tipo_comprobante, total__gt=0)
        if numero_documento_cliente is not "":
            ventas = ventas.filter(comprobante__numero_documento_cliente__icontains=numero_documento_cliente, total__gt=0)
        if numero_comprobante is not "":
            ventas = ventas.filter(comprobante__correlativo=numero_comprobante, total__gt=0)
        if nombre_cliente is not "":
            ventas = ventas.filter(comprobante__nombre_cliente__icontains=nombre_cliente, total__gt=0)

        total_ventas = ventas.count()
        paginator = VentaPagination()
        result_page = paginator.paginate_queryset(ventas, request)
        total_pages = ceil(total_ventas / page_size)

        next_page = page_number + 1 if page_number < total_pages else None
        previous_page = page_number - 1 if page_number > 1 else None

        ventas_json = []
        for venta in result_page:  # type: ignore[reportOptionalIterable]
            comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
            comprobante_json = None

            if comprobante_venta:
                comprobante_json = {
                    "tipo_comprobante": comprobante_venta.tipo_comprobante,
                    "serie": comprobante_venta.serie,
                    "correlativo": comprobante_venta.correlativo,
                    "moneda": comprobante_venta.moneda,
                    "gravadas": float(comprobante_venta.gravadas) if comprobante_venta.gravadas else None,
                    "igv": float(comprobante_venta.igv) if comprobante_venta.igv else None,
                    "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta.valorVenta else None,
                    "sub_total": float(comprobante_venta.sub_total) if comprobante_venta.sub_total else None,
                    "total": float(comprobante_venta.total) if comprobante_venta.total else None,
                    "leyenda": comprobante_venta.leyenda,
                    "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente,
                    "numero_documento_cliente": comprobante_venta.numero_documento_cliente,
                    "nombre_cliente": comprobante_venta.nombre_cliente,
                    "estado_sunat": comprobante_venta.estado_sunat,
                    "xml_url": comprobante_venta.xml_url,
                    "pdf_url": comprobante_venta.pdf_url,
                    "cdr_url": comprobante_venta.cdr_url,
                    "ticket_url": comprobante_venta.ticket_url,
                    "items": comprobante_venta.items,
                }

            # Lectura desde productos_json (ya no VentaProducto) - mantiene compatibilidad de keys
            from apps.venta.utils import _parse_productos_json, VentaService

            raw_productos = _parse_productos_json(venta.productos_json)
            # Enriquecer con is_deleted/is_updated e imagen si falta
            try:
                raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
            except Exception:
                pass
            productos_json = []
            for idx, item in enumerate(raw_productos):
                if not isinstance(item, dict):
                    continue
                # Mapear a formato esperado por frontend (compat con VentaProducto)
                try:
                    cantidad = int(item.get("cantidad", 0) or 0)
                except Exception:
                    try:
                        cantidad = int(float(str(item.get("cantidad", 0))))
                    except Exception:
                        cantidad = 0
                # valores con fallback para compatibilidad
                def _f(v, d=0.0):
                    if v is None or v == "":
                        return d
                    try:
                        return float(v)
                    except Exception:
                        try:
                            return float(str(v).replace(",", "."))
                        except Exception:
                            return d
                productos_json.append({
                    "id": item.get("producto_id") or idx,
                    "producto": item.get("producto_id"),
                    "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                    "producto_nombre": item.get("producto_nombre") or item.get("nombre") or item.get("descripcion"),
                    "cantidad": cantidad,
                    "valor_unitario": _f(item.get("valor_unitario")),
                    "valor_venta": _f(item.get("valor_venta")),
                    "base_igv": _f(item.get("base_igv", item.get("valor_venta"))),
                    "porcentaje_igv": _f(item.get("porcentaje_igv", 18.0)),
                    "igv": _f(item.get("igv")),
                    "tipo_afectacion_igv": item.get("tipo_afectacion_igv", "10"),
                    "total_impuestos": _f(item.get("total_impuestos", item.get("igv"))),
                    "precio_unitario": _f(item.get("precio_unitario", item.get("costo_original"))),
                    "descuento": _f(item.get("descuento")),
                    "costo_original": _f(item.get("costo_original", item.get("precio_venta"))),
                    "sku": item.get("sku"),
                    "is_deleted": item.get("is_deleted", False),
                    "is_updated": item.get("is_updated", False),
                })

            nota_credito = getattr(venta, "nota_credito", None)
            nota_credito_json = None
            if nota_credito:
                nota_credito_json = {
                    "id": nota_credito.id,
                    "serie": nota_credito.serie,
                    "correlativo": nota_credito.correlativo,
                    "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica,
                    "serie_modifica": nota_credito.serie_modifica,
                    "correlativo_modifica": nota_credito.correlativo_modifica,
                    "tipo_motivo": nota_credito.tipo_motivo,
                    "motivo": nota_credito.motivo,
                    "moneda": nota_credito.moneda,
                    "total": float(nota_credito.total),
                    "estado_sunat": nota_credito.estado_sunat,
                    "xml_url": nota_credito.xml_url,
                    "pdf_url": nota_credito.pdf_url,
                    "cdr_url": nota_credito.cdr_url,
                    "fecha_emision": nota_credito.fecha_emision.isoformat(),
                }

            from apps.venta.utils import calcular_total_venta

            ventas_json.append({
                "id": venta.id,
                "usuario": venta.usuario.id if venta.usuario else None,
                "tienda": venta.tienda.id if venta.tienda else None,
                "fecha_hora": venta.fecha_hora.isoformat(),
                "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                "metodo_pago": venta.metodo_pago,
                "estado": venta.estado,
                "activo": venta.activo,
                "tipo_comprobante": venta.tipo_comprobante,
                "productos": productos_json,
                "total": calcular_total_venta(venta),
                "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                "productos_json": json.dumps(venta.productos_json, indent=4),
                "comprobante": comprobante_json,
                "comprobante_nota_credito": nota_credito_json,
                "tipo_documento_cliente": venta.tipo_documento_cliente,
                "numero_documento_cliente": venta.numero_documento_cliente,
                "nombre_cliente": venta.nombre_cliente,
                "email_cliente": venta.email_cliente,
                "telefono_cliente": venta.telefono_cliente,
                "direccion_cliente": venta.direccion_cliente,
            })

        return Response({
            "count": total_ventas,
            "next": next_page,
            "previous": previous_page,
            "index_page": page_number - 1,
            "length_pages": total_pages,
            "results": ventas_json,
        })






 
class SalesTotalsView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        try:
            body = request.data if isinstance(request.data, dict) else {}
 
            page_size = int(request.query_params.get('page_size', 5))
            page_number = int(request.query_params.get('page', 1))

            if page_size < 1:
                page_size = 5
            if page_number < 1:
                page_number = 1

            tienda_id = request.user.tienda_id

            if not tienda_id:
                return Response(
                    {"error": "El usuario no tiene una tienda asignada"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from_date_str = body.get('from_date')
            to_date_str = body.get('to_date')

            if not from_date_str or not to_date_str:
                return Response(
                    {"error": "Los campos 'from_date' y 'to_date' son requeridos (formato: YYYY-MM-DD)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                tz = ZoneInfo("America/Lima")

                from_date_obj = datetime.strptime(from_date_str, '%Y-%m-%d').replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
                )

                to_date_obj = datetime.strptime(to_date_str, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=0, tzinfo=tz
                )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Formato de fecha inválido. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
 
            # --- Filtros opcionales ---
            # Se espera algo como:
            # {
            #   "from_date": "2026-09-01",
            #   "to_date": "2026-09-10",
            #   "page": 1,
            #   "page_size": 5,
            #   "infinity_scroll": false,
            #   "query": {
            #     "metodo_pago": "EFECTIVO",
            #     "tipo_comprobante": "",
            #     "nombre_cliente": "",
            #     "numero_documento_cliente": "",
            #     "numero_comprobante": "",
            #     "estado_sunat": "ACEPTADO"
            #   }
            # }
            filtros = body.get('query')
            if not isinstance(filtros, dict):
                filtros = {}
 
            def val(key):
                v = filtros.get(key)
                if v is None:
                    return None
                v = str(v).strip()
                return v if v else None
 
            metodo_pago = val('metodo_pago')
            tipo_comprobante = val('tipo_comprobante')
            nombre_cliente = val('nombre_cliente')
            numero_documento_cliente = val('numero_documento_cliente')
            numero_comprobante = val('numero_comprobante')
            estado_sunat = val('estado_sunat')
 
            ventas = Venta.objects.filter(
                tienda_id=tienda_id,
                total__gt=0,
                fecha_hora__range=(from_date_obj, to_date_obj)
            )
 
            # --- Filtros que viven directo en Venta ---
            if metodo_pago:
                ventas = ventas.filter(metodo_pago__iexact=metodo_pago)
 
            if tipo_comprobante:
                ventas = ventas.filter(tipo_comprobante__iexact=tipo_comprobante)
 
            if nombre_cliente:
                ventas = ventas.filter(nombre_cliente__icontains=nombre_cliente)
 
            if numero_documento_cliente:
                ventas = ventas.filter(numero_documento_cliente__icontains=numero_documento_cliente)
 
            # --- Filtros que viven en ComprobanteElectronico (relacionado) ---
            if estado_sunat or numero_comprobante:
                comprobantes_qs = ComprobanteElectronico.objects.all()

                if estado_sunat:
                    comprobantes_qs = comprobantes_qs.filter(estado_sunat__iexact=estado_sunat)

                if numero_comprobante:
                    # Soporta buscar por "serie-correlativo", solo serie, o solo correlativo
                    numero_comprobante_limpio = numero_comprobante.replace(' ', '')
                    if '-' in numero_comprobante_limpio:
                        serie_part, correlativo_part = numero_comprobante_limpio.split('-', 1)
                        comprobantes_qs = comprobantes_qs.filter(
                            Q(serie__iexact=serie_part) & Q(correlativo__icontains=correlativo_part)
                        )
                    else:
                        comprobantes_qs = comprobantes_qs.filter(
                            Q(serie__icontains=numero_comprobante_limpio) |
                            Q(correlativo__icontains=numero_comprobante_limpio)
                        )

                venta_ids_match = comprobantes_qs.values_list('venta_id', flat=True)
                ventas = ventas.filter(id__in=venta_ids_match)
 
            total_ventas = ventas.count()
            paginator = VentaPagination()
            paginated_ventas = paginator.paginate_queryset(ventas, request)
 
            total_pages = ceil(total_ventas / page_size)
 
            ventas_json = []
            for venta in paginated_ventas:  # type: ignore[reportOptionalIterable]
                comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
                comprobante_json = None
 
                if comprobante_venta:
                    comprobante_json = {
                        "tipo_comprobante": comprobante_venta.tipo_comprobante,
                        "serie": comprobante_venta.serie,
                        "correlativo": comprobante_venta.correlativo,
                        "moneda": comprobante_venta.moneda,
                        "gravadas": float(comprobante_venta.gravadas) if comprobante_venta.gravadas else None,
                        "igv": float(comprobante_venta.igv) if comprobante_venta.igv else None,
                        "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta.valorVenta else None,
                        "sub_total": float(comprobante_venta.sub_total) if comprobante_venta.sub_total else None,
                        "total": float(comprobante_venta.total) if comprobante_venta.total else None,
                        "leyenda": comprobante_venta.leyenda,
                        "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente,
                        "numero_documento_cliente": comprobante_venta.numero_documento_cliente,
                        "nombre_cliente": comprobante_venta.nombre_cliente,
                        "estado_sunat": comprobante_venta.estado_sunat,
                        "xml_url": comprobante_venta.xml_url,
                        "pdf_url": comprobante_venta.pdf_url,
                        "cdr_url": comprobante_venta.cdr_url,
                        "ticket_url": comprobante_venta.ticket_url,
                        "items": comprobante_venta.items,
                    }
 
                from apps.venta.utils import _parse_productos_json, VentaService
                raw_productos = _parse_productos_json(venta.productos_json)
                try:
                    raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                except Exception:
                    pass
                productos_json = []
                for idx, item in enumerate(raw_productos):
                    if not isinstance(item, dict):
                        continue
                    try:
                        cantidad = int(item.get("cantidad", 0) or 0)
                    except Exception:
                        try:
                            cantidad = int(float(str(item.get("cantidad", 0))))
                        except Exception:
                            cantidad = 0
                    def _f(v, d=0.0):
                        if v is None or v == "":
                            return d
                        try:
                            return float(v)
                        except Exception:
                            try:
                                return float(str(v).replace(",", "."))
                            except Exception:
                                return d
                    productos_json.append({
                        "id": item.get("producto_id") or idx,
                        "producto": item.get("producto_id"),
                        "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                        "producto_nombre": item.get("producto_nombre") or item.get("nombre") or item.get("descripcion"),
                        "cantidad": cantidad,
                        "valor_unitario": _f(item.get("valor_unitario")),
                        "valor_venta": _f(item.get("valor_venta")),
                        "base_igv": _f(item.get("base_igv", item.get("valor_venta"))),
                        "porcentaje_igv": _f(item.get("porcentaje_igv", 18.0)),
                        "igv": _f(item.get("igv")),
                        "tipo_afectacion_igv": item.get("tipo_afectacion_igv", "10"),
                        "total_impuestos": _f(item.get("total_impuestos", item.get("igv"))),
                        "precio_unitario": _f(item.get("precio_unitario", item.get("costo_original"))),
                        "descuento": _f(item.get("descuento")),
                        "costo_original": _f(item.get("costo_original", item.get("precio_venta"))),
                        "sku": item.get("sku"),
                        "is_deleted": item.get("is_deleted", False),
                        "is_updated": item.get("is_updated", False),
                    })
 
                nota_credito = getattr(venta, "nota_credito", None)
                nota_credito_json = None
                if nota_credito:
                    nota_credito_json = {
                        "id": nota_credito.id,
                        "serie": nota_credito.serie,
                        "correlativo": nota_credito.correlativo,
                        "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica,
                        "serie_modifica": nota_credito.serie_modifica,
                        "correlativo_modifica": nota_credito.correlativo_modifica,
                        "tipo_motivo": nota_credito.tipo_motivo,
                        "motivo": nota_credito.motivo,
                        "moneda": nota_credito.moneda,
                        "total": float(nota_credito.total),
                        "estado_sunat": nota_credito.estado_sunat,
                        "xml_url": nota_credito.xml_url,
                        "pdf_url": nota_credito.pdf_url,
                        "cdr_url": nota_credito.cdr_url,
                        "fecha_emision": nota_credito.fecha_emision.isoformat(),
                    }
 
                from apps.venta.utils import calcular_total_venta
 
                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id if venta.tienda else None,
                    "fecha_hora": venta.fecha_hora.isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": calcular_total_venta(venta),
                    "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                    "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                    "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                    "productos_json": json.dumps(venta.productos_json, indent=4),
                    "comprobante": comprobante_json,
                    "comprobante_nota_credito": nota_credito_json,
                    "tipo_documento_cliente": venta.tipo_documento_cliente,
                    "numero_documento_cliente": venta.numero_documento_cliente,
                    "nombre_cliente": venta.nombre_cliente,
                    "email_cliente": venta.email_cliente,
                    "telefono_cliente": venta.telefono_cliente,
                    "direccion_cliente": venta.direccion_cliente,
                })
 
            next_page = page_number + 1 if page_number < total_pages else None
            previous_page = page_number - 1 if page_number > 1 else None

            infinity_scroll = body.get('infinity_scroll', False)

            if infinity_scroll:
                return Response({
                    "count": total_ventas,
                    "has_more": next_page is not None,
                    "next_cursor": next_page,
                    "results": ventas_json,
                }, status=status.HTTP_200_OK)

            return Response({
                "count": total_ventas,
                "next": next_page,
                "previous": previous_page,
                "index_page": page_number - 1,
                "length_pages": total_pages,
                "results": ventas_json,
            }, status=status.HTTP_200_OK)
 
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

















class PaymentMethodsDistributionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            now_dt = timezone.localtime()
            year = request.data.get("year", now_dt.year)
            month = request.data.get("month", now_dt.month)

            ventas = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=year,
                fecha_hora__month=month,
            ).values_list("metodo_pago", flat=True)

            conteo = {}
            for metodo in ventas:
                nombre = metodo if metodo else "No especificado"
                conteo[nombre] = conteo.get(nombre, 0) + 1

            total = sum(conteo.values())

            resultados = []
            for metodo, cantidad in sorted(conteo.items(), key=lambda x: x[1], reverse=True):
                porcentaje = round((cantidad / total) * 100, 2) if total > 0 else 0
                resultados.append({
                    "metodo_pago": metodo,
                    "cantidad": cantidad,
                    "porcentaje": porcentaje,
                })

            return Response({
                "year": year,
                "month": month,
                "total_ventas": total,
                "metodos_pago": resultados,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesSatisfactionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            tienda_id = request.user.tienda_id if hasattr(request.user, 'tienda_id') else (tienda.id if tienda else None)
            now_dt = timezone.localtime()

            year_a = int(request.data.get("year_a", now_dt.year))
            month_a = int(request.data.get("month_a", now_dt.month))
            year_b = int(request.data.get("year_b", now_dt.year))
            month_b = int(request.data.get("month_b", now_dt.month - 1 if now_dt.month > 1 else 12))

            if now_dt.month == 1 and "year_b" not in request.data:
                year_b = now_dt.year - 1

            if not tienda_id:
                return Response({"error": "Se requiere el ID de la tienda."}, status=400)

            from apps.venta.utils import calcular_total_venta

            def _total_mes(year, month):
                qs = Venta.objects.filter(
                    tienda_id=tienda_id,
                    activo=True,
                    estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                    fecha_hora__year=year,
                    fecha_hora__month=month,
                    comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                ).only("productos_json", "total")
                s = 0.0
                for v in qs:
                    s += calcular_total_venta(v)
                return round(s, 2)

            ventas_mes_a = _total_mes(year_a, month_a)
            ventas_mes_b = _total_mes(year_b, month_b)

            if ventas_mes_b > 0:
                porcentaje = round(((ventas_mes_a - ventas_mes_b) / ventas_mes_b) * 100, 2)
            elif ventas_mes_a > 0:
                porcentaje = 100
            else:
                porcentaje = 0

            variacion = round(float(ventas_mes_a) - float(ventas_mes_b), 2)

            return Response({
                "mes_a": {"year": year_a, "month": month_a, "ventas": float(ventas_mes_a)},
                "mes_b": {"year": year_b, "month": month_b, "ventas": float(ventas_mes_b)},
                "porcentaje": porcentaje,
                "variacion": variacion,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda_id = request.user.tienda_id

            tz = ZoneInfo("America/Lima")
            now = datetime.now(tz)
            hoy = now.date()

            from_date_obj = datetime.combine(hoy, time(0, 0, 0), tzinfo=tz)
            to_date_obj = datetime.combine(hoy, time(23, 59, 59), tzinfo=tz)

            ventas = Venta.objects.filter(
                tienda_id=tienda_id,
                fecha_hora__range=(from_date_obj, to_date_obj),
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).select_related(
                "comprobante", "nota_credito", "usuario", "tienda"
            )

            ventas_json = []
            for venta in ventas:
                comprobante_venta = getattr(venta, "comprobante", None)
                comprobante_json = None

                if comprobante_venta:
                    comprobante_json = {
                        "tipo_comprobante": comprobante_venta.tipo_comprobante,
                        "serie": comprobante_venta.serie,
                        "correlativo": comprobante_venta.correlativo,
                        "moneda": comprobante_venta.moneda,
                        "gravadas": float(comprobante_venta.gravadas) if comprobante_venta.gravadas else None,
                        "igv": float(comprobante_venta.igv) if comprobante_venta.igv else None,
                        "valorVenta": float(comprobante_venta.valorVenta) if comprobante_venta.valorVenta else None,
                        "sub_total": float(comprobante_venta.sub_total) if comprobante_venta.sub_total else None,
                        "total": float(comprobante_venta.total) if comprobante_venta.total else None,
                        "leyenda": comprobante_venta.leyenda,
                        "tipo_documento_cliente": comprobante_venta.tipo_documento_cliente,
                        "numero_documento_cliente": comprobante_venta.numero_documento_cliente,
                        "nombre_cliente": comprobante_venta.nombre_cliente,
                        "estado_sunat": comprobante_venta.estado_sunat,
                        "xml_url": comprobante_venta.xml_url,
                        "pdf_url": comprobante_venta.pdf_url,
                        "cdr_url": comprobante_venta.cdr_url,
                        "ticket_url": comprobante_venta.ticket_url,
                        "items": comprobante_venta.items,
                    }

                from apps.venta.utils import _parse_productos_json, VentaService
                raw_productos = _parse_productos_json(venta.productos_json)
                try:
                    raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                except Exception:
                    pass
                productos_json = []
                for idx, item in enumerate(raw_productos):
                    if not isinstance(item, dict):
                        continue
                    try:
                        cantidad = int(item.get("cantidad", 0) or 0)
                    except Exception:
                        try:
                            cantidad = int(float(str(item.get("cantidad", 0))))
                        except Exception:
                            cantidad = 0
                    def _f(v, d=0.0):
                        if v is None or v == "":
                            return d
                        try:
                            return float(v)
                        except Exception:
                            try:
                                return float(str(v).replace(",", "."))
                            except Exception:
                                return d
                    productos_json.append({
                        "id": item.get("producto_id") or idx,
                        "producto": item.get("producto_id"),
                        "producto_nombre": item.get("producto_nombre") or item.get("nombre") or item.get("descripcion"),
                        "cantidad": cantidad,
                        "valor_unitario": _f(item.get("valor_unitario")),
                        "valor_venta": _f(item.get("valor_venta")),
                        "base_igv": _f(item.get("base_igv", item.get("valor_venta"))),
                        "porcentaje_igv": _f(item.get("porcentaje_igv", 18.0)),
                        "igv": _f(item.get("igv")),
                        "tipo_afectacion_igv": item.get("tipo_afectacion_igv", "10"),
                        "total_impuestos": _f(item.get("total_impuestos", item.get("igv"))),
                        "precio_unitario": _f(item.get("precio_unitario", item.get("costo_original"))),
                        "descuento": _f(item.get("descuento")),
                        "costo_original": _f(item.get("costo_original", item.get("precio_venta"))),
                        "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                        "sku": item.get("sku"),
                        "is_deleted": item.get("is_deleted", False),
                    })

                nota_credito = getattr(venta, "nota_credito", None)
                nota_credito_json = None
                if nota_credito:
                    nota_credito_json = {
                        "id": nota_credito.id,
                        "serie": nota_credito.serie,
                        "correlativo": nota_credito.correlativo,
                        "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica,
                        "serie_modifica": nota_credito.serie_modifica,
                        "correlativo_modifica": nota_credito.correlativo_modifica,
                        "tipo_motivo": nota_credito.tipo_motivo,
                        "motivo": nota_credito.motivo,
                        "moneda": nota_credito.moneda,
                        "total": float(nota_credito.total),
                        "estado_sunat": nota_credito.estado_sunat,
                        "xml_url": nota_credito.xml_url,
                        "pdf_url": nota_credito.pdf_url,
                        "cdr_url": nota_credito.cdr_url,
                        "fecha_emision": nota_credito.fecha_emision.isoformat(),
                    }

                from apps.venta.utils import calcular_total_venta

                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id if venta.tienda else None,
                    "fecha_hora": venta.fecha_hora.isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": calcular_total_venta(venta),
                    "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                    "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                    "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                    "productos_json": json.dumps(venta.productos_json, indent=4),
                    "comprobante": comprobante_json,
                    "comprobante_nota_credito": nota_credito_json,
                    "tipo_documento_cliente": venta.tipo_documento_cliente,
                    "numero_documento_cliente": venta.numero_documento_cliente,
                    "nombre_cliente": venta.nombre_cliente,
                    "email_cliente": venta.email_cliente,
                    "telefono_cliente": venta.telefono_cliente,
                    "direccion_cliente": venta.direccion_cliente,
                })

            return Response({"results": ventas_json}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClientesMasFrecuentesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        anio = request.query_params.get("anio")
        mes = request.query_params.get("mes")

        if not anio or not mes:
            return Response(
                {"error": "Los parámetros 'anio' y 'mes' son requeridos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            anio = int(anio)
            mes = int(mes)
        except ValueError:
            return Response(
                {"error": "Los parámetros 'anio' y 'mes' deben ser números enteros."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ventas = (
            Venta.objects
            .filter(
                tienda=tienda,
                fecha_hora__year=anio,
                fecha_hora__month=mes,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )
            .values("numero_documento_cliente", "nombre_cliente", "telefono_cliente")
            .annotate(total_compras=Count("id"))
            .order_by("-total_compras")
        )

        clientes = []
        for v in ventas:
            clientes.append({
                "nombre": v["nombre_cliente"] or "Sin nombre",
                "celular": v["telefono_cliente"] or "Sin celular",
                "total_compras": v["total_compras"]
            })

        return Response({
            "anio": anio,
            "mes": mes,
            "clientes_frecuentes": clientes
        }, status=status.HTTP_200_OK)


class ClientesMasCompraronView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        anio = request.query_params.get("anio")
        mes = request.query_params.get("mes")

        if not anio or not mes:
            return Response(
                {"error": "Los parámetros 'anio' y 'mes' son requeridos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            anio = int(anio)
            mes = int(mes)
        except ValueError:
            return Response(
                {"error": "Los parámetros 'anio' y 'mes' deben ser números enteros."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.venta.utils import calcular_total_venta

        ventas_qs = Venta.objects.filter(
            tienda=tienda,
            fecha_hora__year=anio,
            fecha_hora__month=mes,
            activo=True,
            estado__in=["ACEPTADO", "aceptado", "Aceptado"],
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
        ).only("numero_documento_cliente", "nombre_cliente", "telefono_cliente", "productos_json", "total")

        # Agrupar por cliente sumando productos_json
        agrupado = {}
        for v in ventas_qs:
            key = (v.numero_documento_cliente or "", v.nombre_cliente or "", v.telefono_cliente or "")
            monto = calcular_total_venta(v)
            if key not in agrupado:
                agrupado[key] = {"nombre": v.nombre_cliente, "celular": v.telefono_cliente, "total_gastado": 0.0}
            agrupado[key]["total_gastado"] += monto

        clientes_sorted = sorted(agrupado.values(), key=lambda x: x["total_gastado"], reverse=True)[:10]

        resultado = []
        for c in clientes_sorted:
            resultado.append({
                "nombre": c["nombre"] or "Sin nombre",
                "celular": c["celular"] or "Sin celular",
                "total_gastado": round(float(c["total_gastado"] or 0), 2)
            })

        return Response({
            "anio": anio,
            "mes": mes,
            "top_clientes": resultado
        }, status=status.HTTP_200_OK)