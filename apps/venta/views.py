from collections import Counter
from datetime import timedelta, datetime, time, date
from zoneinfo import ZoneInfo
from decimal import Decimal
from math import ceil
import json

from django.db import transaction
from django.db.models import Sum
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

    def post(self, request, *args, **kwargs):
        tienda_id = request.user.tienda

        today = localtime(now()).date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        current_year = today.year

        ventas_activas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            total__gt=0,
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado"],
        )

        today_sales = (
            ventas_activas
            .filter(fecha_hora__date=today)
            .aggregate(total=Sum("total"))["total"] or 0
        )

        this_week_sales = (
            ventas_activas
            .filter(
                fecha_hora__date__gte=start_of_week,
                fecha_hora__date__lte=today,
                fecha_hora__year=current_year,
            )
            .aggregate(total=Sum("total"))["total"] or 0
        )

        this_month_sales = (
            ventas_activas
            .filter(
                fecha_hora__date__gte=start_of_month,
                fecha_hora__date__lte=today,
                fecha_hora__year=current_year,
            )
            .aggregate(total=Sum("total"))["total"] or 0
        )

        return Response({
            "todaySales": today_sales,
            "thisWeekSales": this_week_sales,
            "thisMonthSales": this_month_sales,
        })


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

        date_range = []
        current_date = from_date_obj
        while current_date <= to_date_obj:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        ventas = Venta.objects.filter(
            total__gt=0,
            tienda=tienda_id,
            fecha_hora__gte=from_date_obj,
            fecha_hora__lte=to_date_obj,
            comprobante__estado_sunat__in=["ACEPTADO", "ANULADO"]
        )

        daily_sales = (
            ventas
            .values('fecha_hora__date')
            .annotate(total_sales=Sum('total'))
            .order_by('fecha_hora__date')
        )

        sales_by_date = {sale['fecha_hora__date']: sale['total_sales'] or 0 for sale in daily_sales}

        sales_date_range = [
            [f"{date.year}, {date.month - 1}, {date.day}", float(sales_by_date.get(date, 0))]
            for date in date_range
        ]

        return Response({"salesDateRangePerDay": sales_date_range}, status=status.HTTP_200_OK)


class TopProductsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tienda = request.user.tienda
        hoy = datetime.now().date()

        from_date = make_aware(datetime.combine(hoy, time.min))
        to_date = make_aware(datetime.combine(hoy, time.max))

        ventas = Venta.objects.filter(
            tienda=tienda,
            activo=True,
            total__gt=0,
            fecha_hora__range=(from_date, to_date)
        )

        venta_productos = VentaProducto.objects.filter(
            venta__in=ventas,
            venta__comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            venta__estado__in=["ACEPTADO", "aceptado"],
        )

        contador = Counter()
        for vp in venta_productos:
            if vp.producto:
                contador[vp.producto.nombre] += vp.cantidad

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
            fecha_hora__range=(from_date, to_date)
        )

        venta_productos = VentaProducto.objects.filter(
            venta__in=ventas,
            venta__comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            venta__estado__in=["ACEPTADO", "aceptado"],
        )

        contador = Counter()
        for vp in venta_productos:
            if vp.producto:
                contador[vp.producto.nombre] += vp.cantidad

        productos_data = [
            {"nombre": nombre, "cantidad_total_vendida": cantidad}
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
        tienda_id = request.user.tienda
        year = int(request.data.get("year", 0))
        month = int(request.data.get("month", 0))
        day = int(request.data.get("day", 0))
        tipo = request.data.get("tipo", "default")

        if not tienda_id:
            return Response({"error": "Se requiere el ID de la tienda."}, status=400)

        ventas_activas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            total__gt=0,
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado"],
            estado__in=["ACEPTADO", "aceptado"],
        )

        today_sales = None
        this_month_sales = None

        try:
            if tipo == "day_month_year":
                selected_date = date(year, month, day)
                today_sales = ventas_activas.filter(
                    fecha_hora__date=selected_date
                ).aggregate(total=Sum("total"))['total'] or 0

            elif tipo == "month_year" and year and month:
                start_of_month = date(year, month, 1)
                if month == 12:
                    end_of_month = date(year + 1, 1, 1)
                else:
                    end_of_month = date(year, month + 1, 1)

                this_month_sales = ventas_activas.filter(
                    fecha_hora__date__gte=start_of_month,
                    fecha_hora__date__lt=end_of_month
                ).aggregate(total=Sum("total"))['total'] or 0

            else:
                return Response({
                    "todaySales": None,
                    "thisMonthSales": None,
                    "tipo": "default"
                })

        except ValueError:
            return Response({"error": "Fecha inválida."}, status=400)

        return Response({
            "todaySales": today_sales,
            "thisMonthSales": this_month_sales,
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

        ventas = Venta.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            total__gt=0,
            comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            fecha_hora__date__gte=desde,
            fecha_hora__date__lte=hoy,
        )

        por_dia = {}
        for v in ventas:
            dia = v.fecha_hora.date().isoformat()
            por_dia[dia] = por_dia.get(dia, 0) + float(v.total)

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
            productos = VentaProducto.objects.filter(venta=venta)

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

            productos_json = [
                {
                    "id": producto.id,
                    "producto": producto.producto.id if producto.producto else None,
                    "producto_nombre": producto.producto.nombre,
                    "cantidad": producto.cantidad,
                    "valor_unitario": float(producto.valor_unitario),
                    "valor_venta": float(producto.valor_venta),
                    "base_igv": float(producto.base_igv),
                    "porcentaje_igv": float(producto.porcentaje_igv),
                    "igv": float(producto.igv),
                    "tipo_afectacion_igv": producto.tipo_afectacion_igv,
                    "total_impuestos": float(producto.total_impuestos),
                    "precio_unitario": float(producto.precio_unitario),
                }
                for producto in productos
            ]

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

            ventas_json.append({
                "id": venta.id,
                "usuario": venta.usuario.id if venta.usuario else None,
                "tienda": venta.tienda.id,
                "fecha_hora": venta.fecha_hora.isoformat(),
                "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                "metodo_pago": venta.metodo_pago,
                "estado": venta.estado,
                "activo": venta.activo,
                "tipo_comprobante": venta.tipo_comprobante,
                "productos": productos_json,
                "total": venta.total,
                "productos_json": json.dumps(venta.productos_json, indent=4),
                "comprobante": comprobante_json,
                "comprobante_nota_credito": nota_credito_json,
            })

        return Response({
            "count": total_ventas,
            "next": next_page,
            "previous": previous_page,
            "index_page": page_number - 1,
            "length_pages": total_pages,
            "results": ventas_json,
            "search_ventas_found": "ventas_found" if total_ventas > 0 else "ventas_not_found",
        })


class SalesTotalsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size', 5))
            page_number = int(request.query_params.get('page', 1))

            tienda_id = request.user.tienda

            from_date_str = request.query_params.get('from_date')
            to_date_str = request.query_params.get('to_date')

            tz = ZoneInfo("America/Lima")

            from_date_obj = datetime.strptime(from_date_str, '%Y-%m-%d').replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
            )

            to_date_obj = datetime.strptime(to_date_str, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59, microsecond=0, tzinfo=tz
            )

            ventas = Venta.objects.filter(
                tienda_id=tienda_id,
                total__gt=0,
                fecha_hora__range=(from_date_obj, to_date_obj)
            )

            total_ventas = ventas.count()
            paginator = VentaPagination()
            paginated_ventas = paginator.paginate_queryset(ventas, request)
            
            total_pages = ceil(total_ventas / page_size)

            ventas_json = []
            for venta in paginated_ventas:  # type: ignore[reportOptionalIterable]
                comprobante_venta = ComprobanteElectronico.objects.filter(venta=venta).first()
                comprobante_json = None
                productos = VentaProducto.objects.filter(venta=venta)

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

                productos_json = [
                    {
                        "id": producto.id,
                        "producto": producto.producto.id if producto.producto else None,
                        "producto_imagen": producto.producto.imagen.url if producto.producto and producto.producto.imagen else None,
                        "producto_nombre": producto.producto.nombre,
                        "cantidad": producto.cantidad,
                        "valor_unitario": float(producto.valor_unitario),
                        "valor_venta": float(producto.valor_venta),
                        "base_igv": float(producto.base_igv),
                        "porcentaje_igv": float(producto.porcentaje_igv),
                        "igv": float(producto.igv),
                        "tipo_afectacion_igv": producto.tipo_afectacion_igv,
                        "total_impuestos": float(producto.total_impuestos),
                        "precio_unitario": float(producto.precio_unitario),
                    }
                    for producto in productos
                ]

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

                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id,
                    "fecha_hora": venta.fecha_hora.isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": venta.total,
                    "subtotal": float(venta.subtotal),
                    "gravado_total": float(venta.gravado_total),
                    "igv_total": float(venta.igv_total),
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

            return Response({
                "count": total_ventas,
                "next": next_page,
                "previous": previous_page,
                "index_page": page_number - 1,
                "length_pages": total_pages,
                "results": ventas_json,
            }, status=status.HTTP_200_OK)

        except Exception as e:
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

            ventas_mes_a = Venta.objects.filter(
                tienda_id=tienda_id,
                activo=True,
                total__gt=0,
                fecha_hora__year=year_a,
                fecha_hora__month=month_a,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).aggregate(total=Sum("total"))["total"] or 0

            ventas_mes_b = Venta.objects.filter(
                tienda_id=tienda_id,
                activo=True,
                total__gt=0,
                fecha_hora__year=year_b,
                fecha_hora__month=month_b,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).aggregate(total=Sum("total"))["total"] or 0

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
            tienda_id = request.user.tienda

            tz = ZoneInfo("America/Lima")
            now = datetime.now(tz)
            hoy = now.date()

            from_date_obj = datetime.combine(hoy, time(0, 0, 0), tzinfo=tz)
            to_date_obj = datetime.combine(hoy, time(23, 59, 59), tzinfo=tz)

            ventas = Venta.objects.filter(
                tienda_id=tienda_id,
                total__gt=0,
                fecha_hora__range=(from_date_obj, to_date_obj),
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado"],
            ).select_related(
                "comprobante", "nota_credito", "usuario", "tienda"
            ).prefetch_related(
                "ventaproducto_set__producto"
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

                productos_json = [
                    {
                        "id": p.id,
                        "producto": p.producto.id if p.producto else None,
                        "producto_nombre": p.producto.nombre if p.producto else None,
                        "cantidad": p.cantidad,
                        "valor_unitario": float(p.valor_unitario),
                        "valor_venta": float(p.valor_venta),
                        "base_igv": float(p.base_igv),
                        "porcentaje_igv": float(p.porcentaje_igv),
                        "igv": float(p.igv),
                        "tipo_afectacion_igv": p.tipo_afectacion_igv,
                        "total_impuestos": float(p.total_impuestos),
                        "precio_unitario": float(p.precio_unitario),
                        "producto_imagen": p.producto.imagen.url if p.producto.imagen else None,
                    }
                    for p in venta.ventaproducto_set.all()
                ]

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

                ventas_json.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id,
                    "fecha_hora": venta.fecha_hora.isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "productos": productos_json,
                    "total": float(venta.total),
                    "subtotal": float(venta.subtotal),
                    "gravado_total": float(venta.gravado_total),
                    "igv_total": float(venta.igv_total),
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