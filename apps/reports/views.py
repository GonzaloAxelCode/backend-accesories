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
from apps.cliente.models import Cliente


class DailySummaryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            from apps.venta.utils import calcular_total_venta

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json", "total", "numero_documento_cliente")

            total_ventas = sum(calcular_total_venta(v) for v in ventas_hoy)
            # need recount because queryset consumed; re-evaluate
            ventas_hoy_qs = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )
            num_comprobantes = ventas_hoy_qs.count()
            clientes_atendidos = (
                ventas_hoy_qs
                .values("numero_documento_cliente")
                .distinct()
                .count()
            )

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_ventas": round(float(total_ventas), 2),
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
            from apps.venta.utils import calcular_total_venta

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

            ventas_mes_actual_qs = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json", "total", "numero_documento_cliente")

            total_ventas_mes = round(sum(calcular_total_venta(v) for v in ventas_mes_actual_qs), 2)

            # recount for counts (queryset already consumed, rebuild)
            ventas_mes_actual_qs2 = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            )
            num_comprobantes = ventas_mes_actual_qs2.count()
            clientes_mes = (
                ventas_mes_actual_qs2
                .values("numero_documento_cliente")
                .distinct()
                .count()
            )

            ventas_mes_anterior_qs = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=prev_year,
                fecha_hora__month=prev_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json", "total")

            total_ventas_mes_anterior = round(sum(calcular_total_venta(v) for v in ventas_mes_anterior_qs), 2)

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
            from collections import defaultdict
            from apps.venta.utils import calcular_total_venta

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("metodo_pago", "productos_json", "total")

            agrupado = defaultdict(lambda: {"num_ventas": 0, "total_soles": 0.0})
            for v in ventas_hoy:
                key = v.metodo_pago or "No especificado"
                agrupado[key]["num_ventas"] += 1
                agrupado[key]["total_soles"] += calcular_total_venta(v)

            metodos = sorted(agrupado.items(), key=lambda x: x[1]["num_ventas"], reverse=True)

            total_transacciones = sum(info["num_ventas"] for _, info in metodos)
            total_general = sum(info["total_soles"] for _, info in metodos)

            metodos_json = []
            for metodo, info in metodos:
                total_metodo = round(float(info["total_soles"] or 0), 2)
                porcentaje_transacciones = round((info["num_ventas"] / total_transacciones) * 100, 2) if total_transacciones > 0 else 0
                porcentaje_monto = round((total_metodo / total_general) * 100, 2) if total_general > 0 else 0
                metodos_json.append({
                    "metodo_pago": metodo or "No especificado",
                    "cantidad_transacciones": info["num_ventas"],
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
            from apps.venta.utils import calcular_total_venta

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)
            hoy = ahora.date()

            hora_inicio = 8
            hora_fin = 23

            inicio = ahora.replace(hour=hora_inicio, minute=0, second=0, microsecond=0)
            fin = ahora.replace(hour=hora_fin, minute=0, second=0, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio,
                fecha_hora__lt=fin,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("fecha_hora", "productos_json", "total")

            horas = {}
            for h in range(hora_inicio, hora_fin):
                horas[h] = {"cantidad_ventas": 0, "total_soles": 0.0}

            for venta in ventas_hoy:
                hora_local = venta.fecha_hora.astimezone(tz).hour
                if hora_local in horas:
                    horas[hora_local]["cantidad_ventas"] += 1
                    horas[hora_local]["total_soles"] += calcular_total_venta(venta)

            hora_pico_cantidad = max(horas, key=lambda h: horas[h]["cantidad_ventas"])
            hora_pico_monto = max(horas, key=lambda h: horas[h]["total_soles"])

            datos_grafico = []
            for h in range(hora_inicio, hora_fin):
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
            from collections import Counter, defaultdict
            from apps.venta.utils import _parse_productos_json, _get_cantidad_safe, _get_precio_unitario_safe

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json")

            contador = Counter()
            totales = defaultdict(float)
            meta = {}  # nombre -> {producto_id, sku}

            for venta in ventas_hoy:
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
                    precio = _get_precio_unitario_safe(item, cantidad)
                    totales[nombre] += round(precio * cantidad, 2)
                    if nombre not in meta:
                        meta[nombre] = {
                            "producto_id": item.get("producto_id"),
                            "sku": item.get("sku") or "Sin SKU",
                        }

            sorted_nombres = sorted(contador.items(), key=lambda x: x[1], reverse=True)[:10]

            productos_json = []
            for idx, (nombre, cant) in enumerate(sorted_nombres, start=1):
                productos_json.append({
                    "posicion": idx,
                    "producto_id": meta[nombre]["producto_id"],
                    "nombre": nombre,
                    "sku": meta[nombre]["sku"] or "Sin SKU",
                    "cantidad_vendida": cant,
                    "total_neto": round(totales.get(nombre, 0.0), 2),
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
            from collections import defaultdict
            from apps.venta.utils import _parse_productos_json, _get_cantidad_safe, _get_precio_unitario_safe

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_hoy = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json")

            agrupado = defaultdict(lambda: {"total_unidades": 0, "ingreso_neto": 0.0, "nombre": None, "codigo": "N/A", "color": None})

            for venta in ventas_hoy:
                for item in _parse_productos_json(venta.productos_json):
                    if not isinstance(item, dict):
                        continue
                    # categoria snapshot guardado en productos_json: categoria_id / categoria_nombre
                    cat_id = item.get("categoria_id")
                    cat_nombre = item.get("categoria_nombre") or "Sin categoría"
                    # fallback si no hay categoria_id pero hay nombre
                    key = cat_id if cat_id is not None else str(cat_nombre).strip()
                    cantidad = _get_cantidad_safe(item)
                    if cantidad is None:
                        continue
                    precio = _get_precio_unitario_safe(item, cantidad)
                    ingreso = round(precio * cantidad, 2)
                    agrupado[key]["total_unidades"] += cantidad
                    agrupado[key]["ingreso_neto"] += ingreso
                    if agrupado[key]["nombre"] is None:
                        agrupado[key]["nombre"] = cat_nombre
                        agrupado[key]["codigo"] = item.get("categoria_codigo") or "N/A"
                        agrupado[key]["color"] = item.get("categoria_color")
                        agrupado[key]["categoria_id"] = cat_id

            # ordenar por ingreso_neto desc
            sorted_cats = sorted(agrupado.items(), key=lambda x: x[1]["ingreso_neto"], reverse=True)

            categorias_json = []
            for idx, (key, cat) in enumerate(sorted_cats, start=1):
                categorias_json.append({
                    "posicion": idx,
                    "categoria_id": cat.get("categoria_id"),
                    "nombre": cat["nombre"] or "Sin categoría",
                    "codigo": cat["codigo"] or "N/A",
                    "color": cat["color"],
                    "total_unidades": cat["total_unidades"],
                    "ingreso_neto": round(float(cat["ingreso_neto"] or 0), 2),
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
            from apps.venta.utils import calcular_total_venta, _parse_productos_json

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            fecha_inicio = request.query_params.get("fecha_inicio")
            fecha_fin = request.query_params.get("fecha_fin")

            if fecha_inicio and fecha_fin:
                from datetime import datetime
                try:
                    inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
                    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
                    inicio_dia = ahora.replace(year=inicio_dt.year, month=inicio_dt.month, day=inicio_dt.day, hour=0, minute=0, second=0, microsecond=0)
                    fin_dia = ahora.replace(year=fin_dt.year, month=fin_dt.month, day=fin_dt.day, hour=23, minute=59, second=59, microsecond=0)
                except ValueError:
                    return Response({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
                fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_qs = Venta.objects.filter(
                tienda=tienda,
                activo=True,
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
            ).select_related("comprobante").order_by("-fecha_hora")

            if not fecha_inicio or not fecha_fin:
                ventas_qs = ventas_qs[:10]

            ventas_hoy = ventas_qs

            ventas_json = []
            for venta in ventas_hoy:
                hora_local = venta.fecha_hora.astimezone(tz)
                hora_12 = hora_local.strftime("%I:%M %p").lstrip("0")

                comprobante = getattr(venta, "comprobante", None)
                serie = comprobante.serie if comprobante else None
                correlativo = comprobante.correlativo if comprobante else None
                numero_comprobante = f"{serie}-{correlativo}" if serie and correlativo else "Sin comprobante"

                productos = _parse_productos_json(venta.productos_json)
                cantidad_productos = 0
                productos_detalle = []
                for item in productos:
                    if isinstance(item, dict):
                        try:
                            cant = int(item.get("cantidad", 0) or 0)
                        except Exception:
                            try:
                                cant = int(float(str(item.get("cantidad", 0))))
                            except Exception:
                                cant = 0
                        cantidad_productos += cant
                        productos_detalle.append({
                            "nombre": item.get("nombre") or item.get("descripcion") or "",
                            "cantidad": cant,
                            "precio_unitario": round(float(item.get("precio_unitario") or item.get("precio") or 0), 2),
                            "subtotal": round(float(item.get("subtotal") or item.get("valor_venta") or 0), 2),
                            "descuento": round(float(item.get("descuento") or 0), 2),
                        })

                comprobante_data = {}
                nota_credito_data = {}
                if comprobante:
                    comprobante_data = {
                        "comprobante_id": comprobante.id,
                        "tipo_comprobante": comprobante.tipo_comprobante or "",
                        "serie": comprobante.serie or "",
                        "correlativo": comprobante.correlativo or "",
                        "numero_comprobante": f"{comprobante.serie}-{comprobante.correlativo}" if comprobante.serie and comprobante.correlativo else "",
                        "fecha_emision": comprobante.fecha_emision.isoformat() if comprobante.fecha_emision else None,
                        "moneda": comprobante.moneda or "",
                        "gravadas": round(float(comprobante.gravadas or 0), 2),
                        "igv": round(float(comprobante.igv or 0), 2),
                        "valor_venta": round(float(comprobante.valorVenta or 0), 2),
                        "sub_total": round(float(comprobante.sub_total or 0), 2),
                        "total": round(float(comprobante.total or 0), 2),
                        "leyenda": comprobante.leyenda or "",
                        "estado_sunat": comprobante.estado_sunat or "",
                        "codigo_hash": comprobante.codigo_hash or "",
                        "xml_url": comprobante.xml_url or "",
                        "pdf_url": comprobante.pdf_url or "",
                        "cdr_url": comprobante.cdr_url or "",
                        "ticket_url": comprobante.ticket_url or "",
                        "descuento_total": round(float(comprobante.descuento_total or 0), 2),
                    }
                    
                    if hasattr(venta, 'nota_credito'):
                        nota_credito = getattr(venta, 'nota_credito', None)
                        if nota_credito:
                            nota_credito_data = {
                                "nota_credito_id": nota_credito.id,
                                "serie": nota_credito.serie or "",
                                "correlativo": nota_credito.correlativo or "",
                                "numero_nota_credito": f"{nota_credito.serie}-{nota_credito.correlativo}" if nota_credito.serie and nota_credito.correlativo else "",
                                "tipo_comprobante_modifica": nota_credito.tipo_comprobante_modifica or "",
                                "serie_modifica": nota_credito.serie_modifica or "",
                                "correlativo_modifica": nota_credito.correlativo_modifica or "",
                                "tipo_motivo": nota_credito.tipo_motivo or "",
                                "motivo": nota_credito.motivo or "",
                                "moneda": nota_credito.moneda or "",
                                "total": round(float(nota_credito.total or 0), 2),
                                "estado_sunat": nota_credito.estado_sunat or "",
                                "fecha_emision": nota_credito.fecha_emision.isoformat() if nota_credito.fecha_emision else None,
                                "xml_url": nota_credito.xml_url or "",
                                "pdf_url": nota_credito.pdf_url or "",
                                "cdr_url": nota_credito.cdr_url or "",
                            }

                ventas_json.append({
                    "venta_id": venta.id,
                    "fecha_hora": venta.fecha_hora.isoformat(),
                    "hora": hora_12,
                    "numero_comprobante": numero_comprobante,
                    "tipo_comprobante": venta.tipo_comprobante or "",
                    "tipo_venta": getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL",
                    "is_pedido": (getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL") == "PEDIDO",
                    "estado": venta.estado or "",
                    "cliente": venta.nombre_cliente or "Cliente general",
                    "tipo_documento_cliente": venta.tipo_documento_cliente or "",
                    "numero_documento_cliente": venta.numero_documento_cliente or "",
                    "email_cliente": venta.email_cliente or "",
                    "telefono_cliente": venta.telefono_cliente or "",
                    "direccion_cliente": venta.direccion_cliente or "",
                    "metodo_pago": venta.metodo_pago or "No especificado",
                    "cantidad_productos": cantidad_productos,
                    "productos": productos_detalle,
                    "subtotal": round(float(venta.subtotal or 0), 2),
                    "gravado_total": round(float(venta.gravado_total or 0), 2),
                    "igv_total": round(float(venta.igv_total or 0), 2),
                    "descuento_total": round(float(venta.descuento_total or 0), 2),
                    "total": round(float(venta.total or 0), 2),
                    "monto": round(calcular_total_venta(venta), 2),
                    "comprobante": comprobante_data,
                    "nota_credito": nota_credito_data,
                })

            response_data = {
                "ventas_recientes": ventas_json,
            }

            if fecha_inicio and fecha_fin:
                response_data["fecha_inicio"] = fecha_inicio
                response_data["fecha_fin"] = fecha_fin
            else:
                response_data["fecha"] = ahora.strftime("%Y-%m-%d")

            return Response(response_data, status=status.HTTP_200_OK)

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
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
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
                    estado__in=["ACEPTADO", "aceptado", "Aceptado"],
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
            from collections import defaultdict
            from apps.venta.utils import calcular_total_venta

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
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__gte=from_date_obj,
                fecha_hora__lte=to_date_obj,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("metodo_pago", "productos_json", "total")

            agrupado = defaultdict(lambda: {"num_ventas": 0, "total_soles": 0.0})
            total_count = 0
            for v in ventas:
                key = v.metodo_pago or "No especificado"
                agrupado[key]["num_ventas"] += 1
                agrupado[key]["total_soles"] += calcular_total_venta(v)
                total_count += 1

            total_general = sum(info["total_soles"] for info in agrupado.values())

            metodos_sorted = sorted(agrupado.items(), key=lambda x: x[1]["total_soles"], reverse=True)

            metodos_json = []
            for metodo, info in metodos_sorted:
                total_metodo = round(float(info["total_soles"] or 0), 2)
                porcentaje = round((total_metodo / total_general) * 100, 2) if total_general > 0 else 0
                metodos_json.append({
                    "metodo_pago": metodo or "No especificado",
                    "num_ventas": info["num_ventas"],
                    "total_soles": total_metodo,
                    "porcentaje": porcentaje,
                })

            return Response(
                {
                    "from_date": from_date,
                    "to_date": to_date,
                    "total_general": round(total_general, 2),
                    "total_ventas": total_count,
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
            from collections import Counter, defaultdict
            from apps.venta.utils import _parse_productos_json, _get_cantidad_safe, _get_precio_unitario_safe

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
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json")

            contador = Counter()
            ingresos = defaultdict(float)
            meta = {}

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
                    precio = _get_precio_unitario_safe(item, cantidad)
                    ingresos[nombre] += round(precio * cantidad, 2)
                    if nombre not in meta:
                        meta[nombre] = {
                            "producto_id": item.get("producto_id"),
                            "sku": item.get("sku"),
                        }

            productos_json = []
            for nombre, cant in sorted(contador.items(), key=lambda x: x[1], reverse=True):
                productos_json.append({
                    "producto_id": meta[nombre]["producto_id"],
                    "nombre": nombre,
                    "sku": meta[nombre]["sku"],
                    "total_unidades": cant,
                    "total_ingresos": round(ingresos.get(nombre, 0.0), 2),
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
            from collections import defaultdict
            from apps.venta.utils import _parse_productos_json, _get_cantidad_safe, _get_precio_unitario_safe

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
                estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                fecha_hora__year=year,
                fecha_hora__month=current_month,
                comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
            ).only("productos_json")

            agrupado = defaultdict(lambda: {"total_unidades": 0, "total_ingresos": 0.0, "nombre": None, "codigo": None})

            for venta in ventas:
                for item in _parse_productos_json(venta.productos_json):
                    if not isinstance(item, dict):
                        continue
                    cat_id = item.get("categoria_id")
                    cat_nombre = item.get("categoria_nombre") or "Sin categoría"
                    key = cat_id if cat_id is not None else str(cat_nombre).strip()
                    cantidad = _get_cantidad_safe(item)
                    if cantidad is None:
                        continue
                    precio = _get_precio_unitario_safe(item, cantidad)
                    ingreso = round(precio * cantidad, 2)
                    agrupado[key]["total_unidades"] += cantidad
                    agrupado[key]["total_ingresos"] += ingreso
                    if agrupado[key]["nombre"] is None:
                        agrupado[key]["nombre"] = cat_nombre
                        agrupado[key]["codigo"] = item.get("categoria_codigo") or None
                        agrupado[key]["categoria_id"] = cat_id

            sorted_cats = sorted(agrupado.items(), key=lambda x: x[1]["total_ingresos"], reverse=True)

            categorias_json = []
            for key, cat in sorted_cats:
                categorias_json.append({
                    "categoria_id": cat.get("categoria_id"),
                    "nombre": cat["nombre"] or "Sin categoría",
                    "codigo": cat["codigo"],
                    "total_unidades": cat["total_unidades"],
                    "total_ingresos": round(float(cat["total_ingresos"] or 0), 2),
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


class DailyCancelledSalesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            import json
            from apps.venta.utils import calcular_total_venta, _parse_productos_json, VentaService

            tienda = request.user.tienda
            tz = ZoneInfo("America/Lima")
            ahora = timezone.now().astimezone(tz)

            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = ahora.replace(hour=23, minute=59, second=59, microsecond=0)

            ventas_anuladas = Venta.objects.filter(
                tienda=tienda,
                estado__in=["ANULADA", "anulada", "Anulada"],
                fecha_hora__gte=inicio_dia,
                fecha_hora__lte=fin_dia,
            ).select_related("comprobante", "nota_credito", "usuario", "tienda").order_by("-fecha_hora")

            total_count = ventas_anuladas.count()
            total_monto = round(sum(calcular_total_venta(v) for v in ventas_anuladas), 2)

            ventas_detalle = []
            for venta in ventas_anuladas:
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
                raw_productos = _parse_productos_json(venta.productos_json)
                try:
                    raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                except Exception:
                    pass
                productos = []
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
                    productos.append({
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
                        "sku": item.get("sku"),
                        "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                        "categoria_id": item.get("categoria_id"),
                        "categoria_nombre": item.get("categoria_nombre"),
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
                ventas_detalle.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id if venta.tienda else None,
                    "fecha_hora": venta.fecha_hora.astimezone(tz).isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.astimezone(tz).isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.astimezone(tz).isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "tipo_venta": getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL",
                    "is_pedido": (getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL") == "PEDIDO",
                    "productos": productos,
                    "total": calcular_total_venta(venta),
                    "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                    "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                    "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                    "descuento_total": float(venta.descuento_total) if venta.descuento_total is not None else None,
                    "productos_json": json.dumps(venta.productos_json, indent=4, ensure_ascii=False) if isinstance(venta.productos_json, (list, dict)) else str(venta.productos_json),
                    "comprobante": comprobante_json,
                    "comprobante_nota_credito": nota_credito_json,
                    "tipo_documento_cliente": venta.tipo_documento_cliente,
                    "numero_documento_cliente": venta.numero_documento_cliente,
                    "nombre_cliente": venta.nombre_cliente,
                    "email_cliente": venta.email_cliente,
                    "telefono_cliente": venta.telefono_cliente,
                    "direccion_cliente": venta.direccion_cliente,
                })

            return Response(
                {
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "total_anuladas": total_count,
                    "total_monto_anulado": total_monto,
                    "ventas": ventas_detalle,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CancelledSalesByDateRangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            import json
            from apps.venta.utils import calcular_total_venta, _parse_productos_json, VentaService

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
                estado__in=["ANULADA", "anulada", "Anulada"],
                fecha_hora__gte=from_date_obj,
                fecha_hora__lte=to_date_obj,
            ).select_related("comprobante", "nota_credito", "usuario", "tienda").order_by("-fecha_hora")

            total_count = ventas.count()
            total_monto = round(sum(calcular_total_venta(v) for v in ventas), 2)

            ventas_detalle = []
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
                raw_productos = _parse_productos_json(venta.productos_json)
                try:
                    raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                except Exception:
                    pass
                productos = []
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
                    productos.append({
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
                        "sku": item.get("sku"),
                        "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                        "categoria_id": item.get("categoria_id"),
                        "categoria_nombre": item.get("categoria_nombre"),
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
                ventas_detalle.append({
                    "id": venta.id,
                    "usuario": venta.usuario.id if venta.usuario else None,
                    "tienda": venta.tienda.id if venta.tienda else None,
                    "fecha_hora": venta.fecha_hora.astimezone(tz).isoformat(),
                    "fecha_realizacion": venta.fecha_realizacion.astimezone(tz).isoformat() if venta.fecha_realizacion else None,
                    "fecha_cancelacion": venta.fecha_cancelacion.astimezone(tz).isoformat() if venta.fecha_cancelacion else None,
                    "metodo_pago": venta.metodo_pago,
                    "estado": venta.estado,
                    "activo": venta.activo,
                    "tipo_comprobante": venta.tipo_comprobante,
                    "tipo_venta": getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL",
                    "is_pedido": (getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL") == "PEDIDO",
                    "productos": productos,
                    "total": calcular_total_venta(venta),
                    "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                    "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                    "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                    "descuento_total": float(venta.descuento_total) if venta.descuento_total is not None else None,
                    "productos_json": json.dumps(venta.productos_json, indent=4, ensure_ascii=False) if isinstance(venta.productos_json, (list, dict)) else str(venta.productos_json),
                    "comprobante": comprobante_json,
                    "comprobante_nota_credito": nota_credito_json,
                    "tipo_documento_cliente": venta.tipo_documento_cliente,
                    "numero_documento_cliente": venta.numero_documento_cliente,
                    "nombre_cliente": venta.nombre_cliente,
                    "email_cliente": venta.email_cliente,
                    "telefono_cliente": venta.telefono_cliente,
                    "direccion_cliente": venta.direccion_cliente,
                })

            return Response(
                {
                    "from_date": from_date,
                    "to_date": to_date,
                    "total_anuladas": total_count,
                    "total_monto_anulado": total_monto,
                    "ventas": ventas_detalle,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClientsSalesHistoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            import json
            from django.db.models import Q, Max
            from apps.venta.utils import calcular_total_venta, _parse_productos_json, VentaService

            tienda = request.user.tienda
            if not tienda:
                return Response({"error": "Usuario sin tienda asignada"}, status=status.HTTP_400_BAD_REQUEST)

            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
            search = (request.query_params.get("search") or "").strip()
            estado_filter = request.query_params.get("estado", "ACEPTADO")
            from_date_str = request.query_params.get("from_date")
            to_date_str = request.query_params.get("to_date")

            base_qs = Venta.objects.filter(tienda=tienda)
            # por defecto solo aceptadas, si se pasa estado=ALL incluir todo
            if estado_filter and estado_filter.upper() != "ALL":
                base_qs = base_qs.filter(
                    estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                    comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                )
            # rango fechas opcional
            tz = ZoneInfo("America/Lima")
            if from_date_str and to_date_str:
                try:
                    from_dt = datetime.strptime(from_date_str, "%Y-%m-%d").replace(tzinfo=tz)
                    to_dt = datetime.strptime(to_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=tz)
                    base_qs = base_qs.filter(fecha_hora__gte=from_dt, fecha_hora__lte=to_dt)
                except Exception:
                    return Response({"error": "from_date/to_date deben ser YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

            # --- NUEVO: traer TODOS los clientes (aunque no tengan ventas) ---
            # clientes base desde tabla Cliente
            clientes_qs = Cliente.objects.filter(tienda=tienda)
            if search:
                clientes_qs = clientes_qs.filter(
                    Q(document__icontains=search) | Q(fullname__icontains=search) | Q(firstname__icontains=search) | Q(lastname__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
                )
            clientes_qs = clientes_qs.order_by("-date_created")
            # también incluir documentos que aparecen en ventas pero no existen como Cliente (ventas anonimas excluidas)
            # para no perder clientes con venta sin registro en Cliente, los unimos al paginado si no se solapan
            venta_docs_existentes = set(
                base_qs.exclude(numero_documento_cliente__isnull=True).exclude(numero_documento_cliente__exact="").exclude(numero_documento_cliente__exact="00000000")
                .values_list("numero_documento_cliente", flat=True).distinct()
            )
            cliente_docs = set(clientes_qs.values_list("document", flat=True))
            docs_solo_venta = [d for d in venta_docs_existentes if d not in cliente_docs and d]
            # filtrar por search también para docs solo venta
            if search:
                docs_solo_venta = [d for d in docs_solo_venta if search.lower() in d.lower() or Venta.objects.filter(tienda=tienda, numero_documento_cliente=d, nombre_cliente__icontains=search).exists()]

            # construir lista total de identificadores para paginar: primero clientes de la tabla, luego docs solo venta (si no se filtra por Cliente)
            total_clientes = clientes_qs.count() + len(docs_solo_venta)
            total_pages = (total_clientes + page_size - 1) // page_size if page_size else 1
            start = (page - 1) * page_size
            end = start + page_size

            # paginado combinado
            # obtenemos slice de clientes_qs y si sobra espacio tomamos de docs_solo_venta
            clientes_page_objs = list(clientes_qs[start:end])
            # si el slice no llena page_size y hay docs_solo_venta, completar
            remaining = page_size - len(clientes_page_objs)
            docs_page = []
            if remaining > 0 and docs_solo_venta:
                # calcular offset para docs_solo_venta según cuanto ya paginamos de clientes
                docs_start = max(0, start - clientes_qs.count())
                # si start está dentro de clientes_qs, docs_start 0, si start ya pasó clientes, ajustar
                if start >= clientes_qs.count():
                    docs_start = start - clientes_qs.count()
                    docs_page = docs_solo_venta[docs_start:docs_start+page_size]
                elif end > clientes_qs.count():
                    docs_page = docs_solo_venta[:remaining]

            resultados = []
            # procesar clientes de la tabla
            for cliente_obj in clientes_page_objs:
                doc = cliente_obj.document
                ultima_venta = Venta.objects.filter(tienda=tienda, numero_documento_cliente=doc).order_by("-fecha_hora").first() if doc else None
                cliente_detalle = {
                    "numero_documento": doc,
                    "tipo_documento": ultima_venta.tipo_documento_cliente if ultima_venta and doc else None,
                    "nombre_cliente": cliente_obj.fullname or (ultima_venta.nombre_cliente if ultima_venta else None),
                    "fullname": cliente_obj.fullname,
                    "firstname": cliente_obj.firstname,
                    "lastname": cliente_obj.lastname,
                    "email": cliente_obj.email,
                    "phone": cliente_obj.phone,
                    "address": cliente_obj.address,
                    "document": cliente_obj.document,
                    "tienda_id": tienda.id if hasattr(tienda, "id") else None,
                    "cliente_id": cliente_obj.id,
                }
                # historial de ventas de este cliente
                ventas_qs = Venta.objects.filter(tienda=tienda, numero_documento_cliente=doc) if doc else Venta.objects.none()
                if estado_filter and estado_filter.upper() != "ALL":
                    ventas_qs = ventas_qs.filter(
                        estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                        comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                    )
                if from_date_str and to_date_str:
                    ventas_qs = ventas_qs.filter(fecha_hora__gte=from_dt, fecha_hora__lte=to_dt)
                ventas_qs = ventas_qs.select_related("comprobante", "nota_credito", "usuario", "tienda").order_by("-fecha_hora")
                is_sale = ventas_qs.exists()
                total_monto_cliente = round(sum(calcular_total_venta(v) for v in ventas_qs), 2) if is_sale else 0.0
                total_ventas_cli = ventas_qs.count()
                # limitar detalle a 50 ventas por cliente para no saturar, pero informar total_ventas
                ventas_detalle = []
                for venta in ventas_qs[:50]:
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
                    raw_productos = _parse_productos_json(venta.productos_json)
                    try:
                        raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                    except Exception:
                        pass
                    productos = []
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
                        productos.append({
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
                            "precio_venta": _f(item.get("precio_venta", item.get("costo_original"))),
                            "sku": item.get("sku"),
                            "producto_imagen": item.get("producto_imagen") or item.get("img_url") or item.get("imagen"),
                            "img_url": item.get("img_url") or item.get("producto_imagen"),
                            "categoria_id": item.get("categoria_id"),
                            "categoria_nombre": item.get("categoria_nombre"),
                            "precio_compra": _f(item.get("precio_compra", item.get("costo_compra"))),
                            "costo_compra": _f(item.get("costo_compra", item.get("precio_compra"))),
                            "is_deleted": item.get("is_deleted", False),
                            "is_updated": item.get("is_updated", False),
                            "updated_fields": item.get("updated_fields", []),
                            "producto_activo": item.get("producto_activo", not item.get("is_deleted", False)),
                            "producto_existe": item.get("producto_existe", not item.get("is_deleted", False)),
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
                            "fecha_emision": nota_credito.fecha_emision.isoformat() if nota_credito.fecha_emision else None,
                        }
                    # comprobante nota incluye descuento_total y items desde productos_json
                    if comprobante_venta:
                        comprobante_json["descuento_total"] = float(comprobante_venta.descuento_total) if comprobante_venta.descuento_total is not None else None
                        comprobante_json["date_created"] = comprobante_venta.date_created.isoformat() if comprobante_venta.date_created else None
                        comprobante_json["fecha_emision"] = comprobante_venta.fecha_emision.isoformat() if comprobante_venta.fecha_emision else None
                    ventas_detalle.append({
                        "id": venta.id,
                        "usuario": venta.usuario.id if venta.usuario else None,
                        "usuario_email": venta.usuario.email if venta.usuario and hasattr(venta.usuario, "email") else None,
                        "tienda": venta.tienda.id if venta.tienda else None,
                        "tienda_nombre": venta.tienda.nombre if venta.tienda and hasattr(venta.tienda, "nombre") else None,
                        "fecha_hora": venta.fecha_hora.astimezone(tz).isoformat() if venta.fecha_hora else None,
                        "fecha_realizacion": venta.fecha_realizacion.astimezone(tz).isoformat() if venta.fecha_realizacion else None,
                        "fecha_cancelacion": venta.fecha_cancelacion.astimezone(tz).isoformat() if venta.fecha_cancelacion else None,
                        "metodo_pago": venta.metodo_pago,
                        "estado": venta.estado,
                        "activo": venta.activo,
                        "tipo_comprobante": venta.tipo_comprobante,
                        "tipo_venta": getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL",
                        "is_pedido": (getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL") == "PEDIDO",
                        "productos": productos,
                        "productos_json": json.dumps(venta.productos_json, indent=2, ensure_ascii=False) if isinstance(venta.productos_json, (list, dict)) else str(venta.productos_json or ""),
                        "productos_json_raw": venta.productos_json,
                        "total": calcular_total_venta(venta),
                        "subtotal": float(venta.subtotal) if venta.subtotal is not None else None,
                        "gravado_total": float(venta.gravado_total) if venta.gravado_total is not None else None,
                        "igv_total": float(venta.igv_total) if venta.igv_total is not None else None,
                        "descuento_total": float(venta.descuento_total) if venta.descuento_total is not None else None,
                        "cliente_json": venta.cliente_json,
                        "tipo_documento_cliente": venta.tipo_documento_cliente,
                        "numero_documento_cliente": venta.numero_documento_cliente,
                        "nombre_cliente": venta.nombre_cliente,
                        "email_cliente": venta.email_cliente,
                        "telefono_cliente": venta.telefono_cliente,
                        "direccion_cliente": venta.direccion_cliente,
                        "comprobante": comprobante_json,
                        "comprobante_nota_credito": nota_credito_json,
                    })

                # fechas reales de primera/ultima compra de este cliente
                primera = ventas_qs.order_by("fecha_hora").first()
                ultima = ventas_qs.order_by("-fecha_hora").first()
                resultados.append({
                    "cliente": cliente_detalle,
                    "is_sale": is_sale,
                    "resumen": {
                        "total_ventas": total_ventas_cli,
                        "total_monto": total_monto_cliente,
                        "primera_compra": primera.fecha_hora.astimezone(tz).isoformat() if primera and primera.fecha_hora else None,
                        "ultima_compra": ultima.fecha_hora.astimezone(tz).isoformat() if ultima and ultima.fecha_hora else None,
                        "is_sale": is_sale,
                    },
                    "historial_ventas": ventas_detalle,
                })

            # --- clientes que solo tienen ventas pero no existen en tabla Cliente (documento huérfano) ---
            for doc in docs_page:
                ultima_venta = Venta.objects.filter(tienda=tienda, numero_documento_cliente=doc).order_by("-fecha_hora").first()
                cliente_detalle = {
                    "numero_documento": doc,
                    "tipo_documento": ultima_venta.tipo_documento_cliente if ultima_venta else None,
                    "nombre_cliente": ultima_venta.nombre_cliente if ultima_venta else None,
                    "fullname": ultima_venta.nombre_cliente if ultima_venta else None,
                    "firstname": None,
                    "lastname": None,
                    "email": ultima_venta.email_cliente if ultima_venta else None,
                    "phone": ultima_venta.telefono_cliente if ultima_venta else None,
                    "address": ultima_venta.direccion_cliente if ultima_venta else None,
                    "document": doc,
                    "tienda_id": tienda.id if hasattr(tienda, "id") else None,
                    "cliente_id": None,
                }
                ventas_qs = Venta.objects.filter(tienda=tienda, numero_documento_cliente=doc)
                if estado_filter and estado_filter.upper() != "ALL":
                    ventas_qs = ventas_qs.filter(
                        estado__in=["ACEPTADO", "aceptado", "Aceptado"],
                        comprobante__estado_sunat__in=["ACEPTADO", "aceptado", "Aceptado"],
                    )
                if from_date_str and to_date_str:
                    ventas_qs = ventas_qs.filter(fecha_hora__gte=from_dt, fecha_hora__lte=to_dt)
                ventas_qs = ventas_qs.select_related("comprobante", "nota_credito", "usuario", "tienda").order_by("-fecha_hora")
                total_monto_cliente = round(sum(calcular_total_venta(v) for v in ventas_qs), 2)
                total_ventas_cli = ventas_qs.count()
                is_sale = True
                # reutilizar misma construcción de ventas_detalle (limitada a 50)
                ventas_detalle2 = []
                for venta in ventas_qs[:50]:
                    # comprobante
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
                            "descuento_total": float(comprobante_venta.descuento_total) if comprobante_venta.descuento_total is not None else None,
                        }
                    raw_productos = _parse_productos_json(venta.productos_json)
                    try:
                        raw_productos = VentaService.enrich_productos_json(raw_productos, request, None, venta)
                    except Exception:
                        pass
                    productos = []
                    for idx, item in enumerate(raw_productos):
                        if not isinstance(item, dict):
                            continue
                        try:
                            cantidad = int(item.get("cantidad", 0) or 0)
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
                        productos.append({
                            "id": item.get("producto_id") or idx,
                            "producto": item.get("producto_id"),
                            "producto_nombre": item.get("producto_nombre") or item.get("nombre"),
                            "cantidad": cantidad,
                            "precio_unitario": _f(item.get("precio_unitario")),
                            "descuento": _f(item.get("descuento")),
                        })
                    ventas_detalle2.append({
                        "id": venta.id,
                        "fecha_hora": venta.fecha_hora.astimezone(tz).isoformat() if venta.fecha_hora else None,
                        "tipo_venta": getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL",
                        "is_pedido": (getattr(venta, "tipo_venta", "PRESENCIAL") or "PRESENCIAL") == "PEDIDO",
                        "total": calcular_total_venta(venta),
                        "productos": productos,
                        "comprobante": comprobante_json,
                    })
                primera = ventas_qs.order_by("fecha_hora").first()
                ultima = ventas_qs.order_by("-fecha_hora").first()
                resultados.append({
                    "cliente": cliente_detalle,
                    "is_sale": True,
                    "resumen": {
                        "total_ventas": total_ventas_cli,
                        "total_monto": total_monto_cliente,
                        "primera_compra": primera.fecha_hora.astimezone(tz).isoformat() if primera and primera.fecha_hora else None,
                        "ultima_compra": ultima.fecha_hora.astimezone(tz).isoformat() if ultima and ultima.fecha_hora else None,
                        "is_sale": True,
                    },
                    "historial_ventas": ventas_detalle2,
                })

            return Response(
                {
                    "total_clientes": total_clientes,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "clientes": resultados,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )