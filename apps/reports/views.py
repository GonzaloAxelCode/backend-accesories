from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum, Count, F
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.venta.models import Venta, VentaProducto
from apps.comprobante.models import ComprobanteElectronico


class MonthlyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            month = int(request.data.get("month", 0))
            year = int(request.data.get("year", 0))

            if month < 0 or month > 11:
                return Response(
                    {"error": "El mes debe estar entre 0 y 11"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if year < 2000:
                return Response(
                    {"error": "El año debe ser mayor a 2000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_month = month + 1

            if month == 0:
                prev_month = 12
                prev_year = year - 1
            else:
                prev_month = month
                prev_year = year

            ventas_mes_actual = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            total_ventas_mes = ventas_mes_actual.aggregate(
                total=Sum("total")
            )["total"] or Decimal("0.00")

            num_comprobantes = ventas_mes_actual.count()

            clientes_mes = (
                ventas_mes_actual
                .values("numero_documento_cliente")
                .distinct()
                .count()
            )

            ventas_mes_anterior = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__year=prev_year,
                fecha_hora__month=prev_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            total_ventas_mes_anterior = ventas_mes_anterior.aggregate(
                total=Sum("total")
            )["total"] or Decimal("0.00")

            if total_ventas_mes_anterior > 0:
                porcentaje_variacion = round(
                    ((float(total_ventas_mes) - float(total_ventas_mes_anterior))
                     / float(total_ventas_mes_anterior)) * 100,
                    2,
                )
            elif total_ventas_mes > 0:
                porcentaje_variacion = 100.0
            else:
                porcentaje_variacion = 0.0

            return Response(
                {
                    "month": month,
                    "year": year,
                    "total_ventas": float(total_ventas_mes),
                    "total_ventas_mes_anterior": float(total_ventas_mes_anterior),
                    "porcentaje_vs_mes_anterior": porcentaje_variacion,
                    "num_comprobantes": num_comprobantes,
                    "clientes_atendidos": clientes_mes,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"error": "month y year deben ser números enteros"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentMethodsByDateRangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            from_date = request.data.get("from_date")
            to_date = request.data.get("to_date")

            if not from_date or not to_date:
                return Response(
                    {"error": "Se requiere from_date y to_date"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if len(from_date) != 3 or len(to_date) != 3:
                return Response(
                    {"error": "from_date y to_date deben ser arrays de 3 elementos [dia, mes, año]"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tz = ZoneInfo("America/Lima")

            from_date_obj = datetime(
                from_date[2], from_date[1], from_date[0],
                hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
            )

            to_date_obj = datetime(
                to_date[2], to_date[1], to_date[0],
                hour=23, minute=59, second=59, microsecond=0, tzinfo=tz
            )

            ventas = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=from_date_obj,
                fecha_hora__lte=to_date_obj,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            metodos = (
                ventas
                .values("metodo_pago")
                .annotate(
                    num_ventas=Count("id"),
                    total_soles=Sum("total"),
                )
                .order_by("-total_soles")
            )

            total_general = sum(float(m["total_soles"] or 0) for m in metodos)

            metodos_json = []
            for m in metodos:
                total_metodo = float(m["total_soles"] or 0)
                porcentaje = round((total_metodo / total_general) * 100, 2) if total_general > 0 else 0
                metodos_json.append({
                    "metodo_pago": m["metodo_pago"] or "No especificado",
                    "num_ventas": m["num_ventas"],
                    "total_soles": total_metodo,
                    "porcentaje": porcentaje,
                })

            return Response(
                {
                    "from_date": from_date,
                    "to_date": to_date,
                    "total_general": round(total_general, 2),
                    "total_ventas": ventas.count(),
                    "metodos_pago": metodos_json,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TopProductsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            month = int(request.data.get("month", 0))
            year = int(request.data.get("year", 0))

            if month < 0 or month > 11:
                return Response(
                    {"error": "El mes debe estar entre 0 y 11"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if year < 2000:
                return Response(
                    {"error": "El año debe ser mayor a 2000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_month = month + 1

            ventas = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            venta_productos = VentaProducto.objects.filter(
                venta__in=ventas,
                producto__isnull=False,
            ).values(
                "producto__id",
                "producto__nombre",
                "producto__sku",
            ).annotate(
                total_unidades=Sum("cantidad"),
                total_ingresos=Sum(F("precio_unitario") * F("cantidad")),
            ).order_by("-total_unidades")

            productos_json = []
            for vp in venta_productos:
                productos_json.append({
                    "producto_id": vp["producto__id"],
                    "nombre": vp["producto__nombre"],
                    "sku": vp["producto__sku"],
                    "total_unidades": vp["total_unidades"],
                    "total_ingresos": float(vp["total_ingresos"] or 0),
                })

            return Response(
                {
                    "month": month,
                    "year": year,
                    "total_productos": len(productos_json),
                    "productos": productos_json,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"error": "month y year deben ser números enteros"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TopCategoriesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            month = int(request.data.get("month", 0))
            year = int(request.data.get("year", 0))

            if month < 0 or month > 11:
                return Response(
                    {"error": "El mes debe estar entre 0 y 11"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if year < 2000:
                return Response(
                    {"error": "El año debe ser mayor a 2000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_month = month + 1

            ventas = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            categorias = VentaProducto.objects.filter(
                venta__in=ventas,
                producto__isnull=False,
                producto__categoria__isnull=False,
            ).values(
                "producto__categoria__id",
                "producto__categoria__nombre",
                "producto__categoria__siglas_nombre_categoria",
            ).annotate(
                total_unidades=Sum("cantidad"),
                total_ingresos=Sum(F("precio_unitario") * F("cantidad")),
            ).order_by("-total_ingresos")

            categorias_json = []
            for cat in categorias:
                categorias_json.append({
                    "categoria_id": cat["producto__categoria__id"],
                    "nombre": cat["producto__categoria__nombre"],
                    "codigo": cat["producto__categoria__siglas_nombre_categoria"],
                    "total_unidades": cat["total_unidades"],
                    "total_ingresos": float(cat["total_ingresos"] or 0),
                })

            return Response(
                {
                    "month": month,
                    "year": year,
                    "total_categorias": len(categorias_json),
                    "categorias": categorias_json,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"error": "month y year deben ser números enteros"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )