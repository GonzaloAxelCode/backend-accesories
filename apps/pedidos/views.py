from decimal import Decimal
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo
import json

from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from django.utils.timezone import make_aware

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.venta.utils import ClienteService, VentaService
from apps.inventario.models import Inventario
from .models import Pedido, PedidoProducto


class PedidoPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class CrearPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            tienda = request.user.tienda
            usuario = request.user
            cliente_data = ClienteService.resolve_cliente(data.get("cliente"), tienda)

            fecha_hora = timezone.now()
            observaciones = data.get("observaciones", "")

            # Generar numero_pedido
            tz = ZoneInfo("America/Lima")
            now = datetime.now(tz)
            prefijo = f"PED-{now.strftime('%Y%m')}"
            ultimo = Pedido.objects.filter(
                numero_pedido__startswith=prefijo
            ).order_by('-numero_pedido').first()

            if ultimo:
                try:
                    ultimo_correlativo = int(ultimo.numero_pedido.split('-')[-1])
                except (ValueError, IndexError):
                    ultimo_correlativo = 0
                nuevo_correlativo = ultimo_correlativo + 1
            else:
                nuevo_correlativo = 1

            numero_pedido = f"{prefijo}-{nuevo_correlativo:04d}"

            productos_registrados = []
            subtotal = Decimal("0.00")
            gravado_total = Decimal("0.00")
            igv_total = Decimal("0.00")
            total = Decimal("0.00")

            with transaction.atomic():
                pedido = Pedido.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    metodo_pago=data.get("metodoPago"),
                    fecha_hora=fecha_hora,
                    estado="COTIZADO",
                    numero_pedido=numero_pedido,
                    observaciones=observaciones,
                    tipo_documento_cliente=cliente_data.get("tipo_documento", "1"),
                    numero_documento_cliente=cliente_data.get("numero"),
                    nombre_cliente=cliente_data.get("nombre_completo"),
                    email_cliente=cliente_data.get("correo_cliente"),
                    telefono_cliente=cliente_data.get("telefono_cliente"),
                    direccion_cliente=cliente_data.get("direccion_cliente"),
                )

                for item in data["productos"]:
                    inventario_id = item["inventarioId"]
                    cantidad = int(item["cantidad_final"])
                    descuento = Decimal(item.get("descuento", 0))

                    try:
                        inventario = Inventario.objects.get(id=inventario_id)
                    except Inventario.DoesNotExist:
                        return Response(
                            {"error": f"Inventario {inventario_id} no encontrado"},
                            status=status.HTTP_404_NOT_FOUND,
                        )

                    # Verificar stock (sin bloquear ni descontar)
                    stock_ok = inventario.cantidad >= cantidad

                    precio_unitario_original = Decimal(inventario.costo_venta)
                    precio_unitario = precio_unitario_original - (descuento / cantidad)
                    valor_unitario = precio_unitario / (Decimal("1.00") + Decimal("0.18"))
                    valor_venta = valor_unitario * cantidad
                    igv = valor_venta * Decimal("0.18")

                    PedidoProducto.objects.create(
                        pedido=pedido,
                        producto=inventario.producto,
                        cantidad=cantidad,
                        stock_disponible=stock_ok,
                        valor_unitario=valor_unitario,
                        valor_venta=valor_venta,
                        base_igv=valor_venta,
                        porcentaje_igv=Decimal("18.00"),
                        igv=igv,
                        tipo_afectacion_igv="10",
                        total_impuestos=igv,
                        precio_unitario=precio_unitario,
                        descuento=descuento,
                        costo_original=precio_unitario_original,
                    )

                    subtotal += valor_venta
                    gravado_total += valor_venta
                    igv_total += igv
                    total += precio_unitario * cantidad

                    productos_registrados.append({
                        "producto_id": inventario.producto.id,
                        "producto_nombre": inventario.producto.nombre,
                        "cantidad": cantidad,
                        "stock_disponible": stock_ok,
                        "valor_unitario": float(valor_unitario),
                        "valor_venta": float(valor_venta),
                        "igv": float(igv),
                        "precio_unitario": float(precio_unitario),
                        "costo_original": float(precio_unitario_original),
                        "descuento": float(descuento),
                    })

                pedido.subtotal = subtotal
                pedido.gravado_total = gravado_total
                pedido.igv_total = igv_total
                pedido.total = total
                pedido.productos_json = productos_registrados
                pedido.save()

            return Response({
                "pedido": {
                    "id": pedido.id,
                    "numero_pedido": pedido.numero_pedido,
                    "estado": pedido.estado,
                    "metodo_pago": pedido.metodo_pago,
                    "total": float(pedido.total),
                    "subtotal": float(pedido.subtotal),
                    "igv_total": float(pedido.igv_total),
                    "nombre_cliente": pedido.nombre_cliente,
                "fecha_hora": pedido.fecha_hora.isoformat() if pedido.fecha_hora else None,
                    "observaciones": pedido.observaciones,
                    "productos": productos_registrados,
                }
            }, status=status.HTTP_201_CREATED)

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
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListaPedidosView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tienda_id = request.user.tienda
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")

        if not from_date or not to_date:
            return Response(
                {"error": "Se debe proporcionar un rango de fechas válido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tz = ZoneInfo("America/Lima")

        # Soporta formato array [year, month, day] (mes 0-indexed) o string "YYYY-MM-DD"
        if isinstance(from_date, list):
            from_date_obj = make_aware(
                datetime(from_date[0], from_date[1] + 1, from_date[2], 0, 0, 0),
                timezone=tz,
            )
        else:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
            )

        if isinstance(to_date, list):
            to_date_obj = make_aware(
                datetime(to_date[0], to_date[1] + 1, to_date[2], 23, 59, 59),
                timezone=tz,
            )
        else:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=0, tzinfo=tz
            )

        pedidos = Pedido.objects.filter(
            tienda_id=tienda_id,
            activo=True,
            fecha_hora__range=(from_date_obj, to_date_obj),
        ).select_related(
            "usuario", "tienda"
        ).prefetch_related(
            "pedidoproducto_set__producto"
        )

        pedidos_json = []
        for pedido in pedidos:
            productos = []
            for pp in pedido.pedidoproducto_set.all():
                productos.append({
                    "id": pp.id,
                    "producto": pp.producto.id if pp.producto else None,
                    "producto_nombre": pp.producto.nombre if pp.producto else None,
                    "cantidad": pp.cantidad,
                    "stock_disponible": pp.stock_disponible,
                    "valor_unitario": float(pp.valor_unitario),
                    "valor_venta": float(pp.valor_venta),
                    "igv": float(pp.igv),
                    "precio_unitario": float(pp.precio_unitario),
                    "costo_original": float(pp.costo_original),
                    "descuento": float(pp.descuento),
                })

            pedidos_json.append({
                "id": pedido.id,
                "numero_pedido": pedido.numero_pedido,
                "usuario": pedido.usuario.id if pedido.usuario else None,
                "tienda": pedido.tienda.id if pedido.tienda else None,
                "fecha_hora": pedido.fecha_hora.isoformat(),
                "metodo_pago": pedido.metodo_pago,
                "estado": pedido.estado,
                "activo": pedido.activo,
                "total": float(pedido.total),
                "subtotal": float(pedido.subtotal),
                "gravado_total": float(pedido.gravado_total),
                "igv_total": float(pedido.igv_total),
                "descuento_total": float(pedido.descuento_total),
                "nombre_cliente": pedido.nombre_cliente,
                "numero_documento_cliente": pedido.numero_documento_cliente,
                "email_cliente": pedido.email_cliente,
                "telefono_cliente": pedido.telefono_cliente,
                "direccion_cliente": pedido.direccion_cliente,
                "observaciones": pedido.observaciones,
                "productos": productos,
                "productos_json": pedido.productos_json,
                "date_created": pedido.date_created.isoformat() if pedido.date_created else None,
            })

        return Response({
            "count": len(pedidos_json),
            "results": pedidos_json,
        }, status=status.HTTP_200_OK)


class BuscarPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        page_number = int(request.data.get('page', 1))
        page_size = int(request.data.get('page_size', 5))
        tienda_id = request.user.tienda
        query = request.data.get('query', {})

        pedidos = Pedido.objects.filter(tienda_id=tienda_id, activo=True)

        from_date = query.get('from_date')
        to_date = query.get('to_date')

        if from_date and to_date:
            tz = ZoneInfo("America/Lima")

            from_date_obj = make_aware(
                datetime(from_date[0], from_date[1] + 1, from_date[2], 0, 0, 0),
                timezone=tz,
            )
            to_date_obj = make_aware(
                datetime(to_date[0], to_date[1] + 1, to_date[2], 23, 59, 59),
                timezone=tz,
            )
            pedidos = pedidos.filter(fecha_hora__range=(from_date_obj, to_date_obj))

        numero_pedido = query.get('numero_pedido')
        metodo_pago = query.get('metodo_pago')
        estado = query.get('estado')
        nombre_cliente = query.get('nombre_cliente')
        numero_documento_cliente = query.get('numero_documento_cliente')
        stock_disponible = query.get('stock_disponible')

        if numero_pedido is not "":
            pedidos = pedidos.filter(numero_pedido__icontains=numero_pedido)
        if metodo_pago is not "":
            pedidos = pedidos.filter(metodo_pago__icontains=metodo_pago)
        if estado is not "":
            pedidos = pedidos.filter(estado__icontains=estado)
        if nombre_cliente is not "":
            pedidos = pedidos.filter(nombre_cliente__icontains=nombre_cliente)
        if numero_documento_cliente is not "":
            pedidos = pedidos.filter(numero_documento_cliente__icontains=numero_documento_cliente)
        if stock_disponible is not "":
            stock_bool = stock_disponible.lower() == 'true' if isinstance(stock_disponible, str) else bool(stock_disponible)
            if stock_bool:
                pedidos = pedidos.filter(pedidoproducto__stock_disponible=True).distinct()
            else:
                pedidos = pedidos.filter(pedidoproducto__stock_disponible=False).distinct()

        total_pedidos = pedidos.count()
        paginator = PedidoPagination()
        result_page = paginator.paginate_queryset(pedidos, request)
        total_pages = ceil(total_pedidos / page_size) if page_size > 0 else 0

        next_page = page_number + 1 if page_number < total_pages else None
        previous_page = page_number - 1 if page_number > 1 else None

        pedidos_json = []
        for pedido in result_page:
            productos = PedidoProducto.objects.filter(pedido=pedido)
            productos_json = [
                {
                    "id": p.id,
                    "producto": p.producto.id if p.producto else None,
                    "producto_nombre": p.producto.nombre if p.producto else None,
                    "cantidad": p.cantidad,
                    "stock_disponible": p.stock_disponible,
                    "valor_unitario": float(p.valor_unitario),
                    "valor_venta": float(p.valor_venta),
                    "igv": float(p.igv),
                    "precio_unitario": float(p.precio_unitario),
                    "costo_original": float(p.costo_original),
                    "descuento": float(p.descuento),
                }
                for p in productos
            ]

            pedidos_json.append({
                "id": pedido.id,
                "numero_pedido": pedido.numero_pedido,
                "usuario": pedido.usuario.id if pedido.usuario else None,
                "tienda": pedido.tienda.id if pedido.tienda else None,
                "fecha_hora": pedido.fecha_hora.isoformat(),
                "fecha_realizacion": pedido.fecha_realizacion.isoformat() if pedido.fecha_realizacion else None,
                "fecha_cancelacion": pedido.fecha_cancelacion.isoformat() if pedido.fecha_cancelacion else None,
                "metodo_pago": pedido.metodo_pago,
                "estado": pedido.estado,
                "activo": pedido.activo,
                "total": float(pedido.total),
                "subtotal": float(pedido.subtotal),
                "gravado_total": float(pedido.gravado_total),
                "igv_total": float(pedido.igv_total),
                "descuento_total": float(pedido.descuento_total),
                "nombre_cliente": pedido.nombre_cliente,
                "numero_documento_cliente": pedido.numero_documento_cliente,
                "email_cliente": pedido.email_cliente,
                "telefono_cliente": pedido.telefono_cliente,
                "direccion_cliente": pedido.direccion_cliente,
                "observaciones": pedido.observaciones,
                "productos": productos_json,
                "productos_json": pedido.productos_json,
                "date_created": pedido.date_created.isoformat() if pedido.date_created else None,
            })

        return Response({
            "count": total_pedidos,
            "next": next_page,
            "previous": previous_page,
            "index_page": page_number - 1,
            "length_pages": total_pages,
            "results": pedidos_json,
            "search_pedidos_found": "pedidos_found" if total_pedidos > 0 else "pedidos_not_found",
        })


class CancelarPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pedido_id):
        try:
            tienda_id = request.user.tienda

            try:
                pedido = Pedido.objects.get(id=pedido_id, tienda_id=tienda_id, activo=True)
            except Pedido.DoesNotExist:
                return Response(
                    {"error": "Pedido no encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if pedido.estado == "CANCELADO":
                return Response(
                    {"error": "El pedido ya está cancelado"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pedido.estado = "CANCELADO"
            pedido.fecha_cancelacion = timezone.now()
            pedido.save()

            return Response({
                "mensaje": "Pedido cancelado exitosamente",
                "pedido": {
                    "id": pedido.id,
                    "numero_pedido": pedido.numero_pedido,
                    "estado": pedido.estado,
                    "fecha_cancelacion": pedido.fecha_cancelacion.isoformat(),
                    "total": float(pedido.total),
                    "nombre_cliente": pedido.nombre_cliente,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
