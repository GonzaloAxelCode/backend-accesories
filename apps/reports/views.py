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


class DailySummaryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            total_ventas = ventas_hoy.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
            num_comprobantes = ventas_hoy.count()
            clientes_atendidos = (
                ventas_hoy
                .values("numero_documento_cliente")
                .distinct()
                .count()
            )

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_ventas": float(total_ventas),
                    "comprobantes_emitidos": num_comprobantes,
                    "clientes_atendidos": clientes_atendidos,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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


class DailyPaymentMethodsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            metodos = (
                ventas_hoy
                .values("metodo_pago")
                .annotate(
                    num_ventas=Count("id"),
                    total_soles=Sum("total"),
                )
                .order_by("-num_ventas")
            )

            total_transacciones = sum(m["num_ventas"] for m in metodos)
            total_general = sum(float(m["total_soles"] or 0) for m in metodos)

            metodos_json = []
            for m in metodos:
                total_metodo = float(m["total_soles"] or 0)
                porcentaje_transacciones = round((m["num_ventas"] / total_transacciones) * 100, 2) if total_transacciones > 0 else 0
                porcentaje_monto = round((total_metodo / total_general) * 100, 2) if total_general > 0 else 0
                metodos_json.append({
                    "metodo_pago": m["metodo_pago"] or "No especificado",
                    "cantidad_transacciones": m["num_ventas"],
                    "total_soles": total_metodo,
                    "porcentaje_transacciones": porcentaje_transacciones,
                    "porcentaje_monto": porcentaje_monto,
                })

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_transacciones": total_transacciones,
                    "total_general_soles": round(total_general, 2),
                    "metodos_pago": metodos_json,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyPeakHoursReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)
            hoy = ahora.date()

            hora_inicio = 9
            hora_fin = 21

            inicio = ahora.replace(hour=hora_inicio, minute=0, second=0, microsecond=0)
            fin = ahora.replace(hour=hora_fin, minute=0, second=0, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio,
                fecha_hora__lt=fin,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            horas = {}
            for h in range(hora_inicio, hora_inicio + 12):
                horas[h] = {"cantidad_ventas": 0, "total_soles": 0.0}

            for venta in ventas_hoy:
                hora_local = venta.fecha_hora.astimezone(tz).hour
                if hora_local in horas:
                    horas[hora_local]["cantidad_ventas"] += 1
                    horas[hora_local]["total_soles"] += float(venta.total)

            hora_pico_cantidad = max(horas, key=lambda h: horas[h]["cantidad_ventas"])
            hora_pico_monto = max(horas, key=lambda h: horas[h]["total_soles"])

            datos_grafico = []
            for h in range(hora_inicio, hora_inicio + 12):
                label = f"{h:02d}:00"
                datos_grafico.append({
                    "hora": h,
                    "label": label,
                    "cantidad_ventas": horas[h]["cantidad_ventas"],
                    "total_soles": round(horas[h]["total_soles"], 2),
                })

            return Response(
                {
                    "fecha": hoy.isoformat(),
                    "hora_pico_ventas": {
                        "hora": hora_pico_cantidad,
                        "label": f"{hora_pico_cantidad:02d}:00",
                        "cantidad_ventas": horas[hora_pico_cantidad]["cantidad_ventas"],
                        "total_soles": round(horas[hora_pico_cantidad]["total_soles"], 2),
                    },
                    "hora_pico_monto": {
                        "hora": hora_pico_monto,
                        "label": f"{hora_pico_monto:02d}:00",
                        "cantidad_ventas": horas[hora_pico_monto]["cantidad_ventas"],
                        "total_soles": round(horas[hora_pico_monto]["total_soles"], 2),
                    },
                    "horas": datos_grafico,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyTopProductsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            top_productos = (
                VentaProducto.objects.filter(
                    venta__in=ventas_hoy,
                    producto__isnull=False,
                )
                .values(
                    "producto__id",
                    "producto__nombre",
                    "producto__sku",
                )
                .annotate(
                    cantidad_vendida=Sum("cantidad"),
                    total_neto=Sum("valor_venta"),
                )
                .order_by("-cantidad_vendida")[:10]
            )

            productos_json = []
            for idx, vp in enumerate(top_productos, start=1):
                productos_json.append({
                    "posicion": idx,
                    "producto_id": vp["producto__id"],
                    "nombre": vp["producto__nombre"],
                    "sku": vp["producto__sku"] or "Sin SKU",
                    "cantidad_vendida": vp["cantidad_vendida"],
                    "total_neto": float(vp["total_neto"] or 0),
                })

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_productos": len(productos_json),
                    "productos": productos_json,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyTopCategoriesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            categorias = (
                VentaProducto.objects.filter(
                    venta__in=ventas_hoy,
                    producto__isnull=False,
                    producto__categoria__isnull=False,
                )
                .values(
                    "producto__categoria__id",
                    "producto__categoria__nombre",
                    "producto__categoria__siglas_nombre_categoria",
                    "producto__categoria__color",
                )
                .annotate(
                    total_unidades=Sum("cantidad"),
                    ingreso_neto=Sum("valor_venta"),
                )
                .order_by("-ingreso_neto")
            )

            categorias_json = []
            for idx, cat in enumerate(categorias, start=1):
                categorias_json.append({
                    "posicion": idx,
                    "categoria_id": cat["producto__categoria__id"],
                    "nombre": cat["producto__categoria__nombre"],
                    "codigo": cat["producto__categoria__siglas_nombre_categoria"] or "N/A",
                    "color": cat["producto__categoria__color"],
                    "total_unidades": cat["total_unidades"],
                    "ingreso_neto": float(cat["ingreso_neto"] or 0),
                })

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_categorias": len(categorias_json),
                    "categorias": categorias_json,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyRecentSalesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = (
                Venta.objects.filter(
                    tienda=tienda,
                    activo=True,
                    total__gt=0,
                    fecha_hora__gte=inicio_dia,
                    fecha_hora__lte=fin_dia,
                    comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                )
                .select_related("comprobante")
                .order_by("-fecha_hora")[:5]
            )

            ventas_json = []
            for venta in ventas_hoy:
                hora_local = venta.fecha_hora.astimezone(tz)
                hora_12 = hora_local.strftime("%I:%M %p").lstrip("0")

                comprobante = getattr(venta, "comprobante", None)
                serie = comprobante.serie if comprobante else None
                correlativo = comprobante.correlativo if comprobante else None
                numero_comprobante = f"{serie}-{correlativo}" if serie and correlativo else "Sin comprobante"

                cantidad_productos = VentaProducto.objects.filter(venta=venta).aggregate(
                    total=Sum("cantidad")
                )["total"] or 0

                ventas_json.append({
                    "venta_id": venta.id,
                    "numero_comprobante": numero_comprobante,
                    "cliente": venta.nombre_cliente or "Cliente general",
                    "hora": hora_12,
                    "monto": float(venta.total),
                    "cantidad_productos": cantidad_productos,
                    "metodo_pago": venta.metodo_pago or "No especificado",
                })

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "ventas_recientes": ventas_json,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyCustomersReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            clientes_hoy = (
                ventas_hoy
                .values("numero_documento_cliente")
                .distinct()
            )

            documentos_hoy = [
                c["numero_documento_cliente"]
                for c in clientes_hoy
                if c["numero_documento_cliente"]
            ]

            clientes_nuevos = 0
            clientes_recurrentes = 0

            for doc in documentos_hoy:
                compras_anteriores = Venta.objects.filter(
                    tienda=tienda,
                    activo=True,
                    total__gt=0,
                    numero_documento_cliente=doc,
                    fecha_hora__lt=inicio_dia,
                    comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                ).exists()

                if compras_anteriores:
                    clientes_recurrentes += 1
                else:
                    clientes_nuevos += 1

            total_clientes = clientes_nuevos + clientes_recurrentes
            porcentaje_recurrentes = round((clientes_recurrentes / total_clientes) * 100, 2) if total_clientes > 0 else 0
            porcentaje_nuevos = round((clientes_nuevos / total_clientes) * 100, 2) if total_clientes > 0 else 0

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_clientes": total_clientes,
                    "clientes_nuevos": clientes_nuevos,
                    "clientes_recurrentes": clientes_recurrentes,
                    "porcentaje_nuevos": porcentaje_nuevos,
                    "porcentaje_recurrentes": porcentaje_recurrentes,
                    "tasa_retencion": porcentaje_recurrentes,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MonthlyCustomersReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")

            now_dt = timezone.now().astimezone(tz)
            year = int(request.data.get("year", now_dt.year))
            month = int(request.data.get("month", now_dt.month))

            inicio_mes = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
            if month == 12:
                fin_mes = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tz)
            else:
                fin_mes = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=tz)

            ventas_mes = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                total__gt=0,
                fecha_hora__gte=inicio_mes,
                fecha_hora__lt=fin_mes,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )

            clientes_mes = (
                ventas_mes
                .values("numero_documento_cliente")
                .distinct()
            )

            documentos_mes = [
                c["numero_documento_cliente"]
                for c in clientes_mes
                if c["numero_documento_cliente"]
            ]

            clientes_nuevos = 0
            clientes_recurrentes = 0

            for doc in documentos_mes:
                compras_anteriores = Venta.objects.filter(
                    tienda=tienda,
                    activo=True,
                    total__gt=0,
                    numero_documento_cliente=doc,
                    fecha_hora__lt=inicio_mes,
                    comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                ).exists()

                if compras_anteriores:
                    clientes_recurrentes += 1
                else:
                    clientes_nuevos += 1

            total_clientes = clientes_nuevos + clientes_recurrentes
            porcentaje_recurrentes = round((clientes_recurrentes / total_clientes) * 100, 2) if total_clientes > 0 else 0
            porcentaje_nuevos = round((clientes_nuevos / total_clientes) * 100, 2) if total_clientes > 0 else 0

            return Response(
                {
                    "year": year,
                    "month": month,
                    "total_clientes": total_clientes,
                    "clientes_nuevos": clientes_nuevos,
                    "clientes_recurrentes": clientes_recurrentes,
                    "porcentaje_nuevos": porcentaje_nuevos,
                    "porcentaje_recurrentes": porcentaje_recurrentes,
                    "tasa_retencion": porcentaje_recurrentes,
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