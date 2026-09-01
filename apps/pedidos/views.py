from decimal import Decimal, InvalidOperation
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_aware

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

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

            fecha_hora = timezone.now()
            observaciones = data.get("observaciones", "")
            notas_internas = data.get("notas_internas", "")

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

            # Datos del cliente
            cliente_data = data.get("cliente", {})

            # Tipo de pedido y canal
            tipo_pedido = data.get("tipo_pedido", "MOSTRADOR")
            canal_venta = data.get("canal_venta", "PRESENCIAL")
            prioridad = data.get("prioridad", "NORMAL")

            # Dirección de envío (si es delivery)
            direccion_envio = data.get("direccion_envio", "")
            referencia_ubicacion = data.get("referencia_ubicacion", "")
            costo_envio = Decimal(str(data.get("costo_envio", 0)))

            # Referencia externa
            referencia_externa = data.get("referencia_externa", "")

            productos_registrados = []
            subtotal = Decimal("0.00")
            gravado_total = Decimal("0.00")
            igv_total = Decimal("0.00")
            total = Decimal("0.00")

            with transaction.atomic():
                pedido = Pedido.objects.create(
                    usuario=usuario,
                    tienda=tienda,
                    numero_pedido=numero_pedido,
                    tipo_pedido=tipo_pedido,
                    canal_venta=canal_venta,
                    prioridad=prioridad,
                    metodo_pago=data.get("metodoPago"),
                    fecha_hora=fecha_hora,
                    estado="COTIZADO",
                    observaciones=observaciones,
                    notas_internas=notas_internas,
                    tipo_documento_cliente=cliente_data.get("tipo_documento", "1"),
                    numero_documento_cliente=cliente_data.get("numero"),
                    nombre_cliente=cliente_data.get("nombre_completo"),
                    email_cliente=cliente_data.get("correo_cliente"),
                    telefono_cliente=cliente_data.get("telefono_cliente"),
                    direccion_envio=direccion_envio,
                    referencia_ubicacion=referencia_ubicacion,
                    costo_envio=costo_envio,
                    referencia_externa=referencia_externa,
                )

                for item in data["productos"]:
                    inventario_id = item["inventarioId"]
                    # cantidad y descuento defensivos (evita TypeError/Decimal(None))
                    raw_cant = item.get("cantidad_final")
                    if raw_cant is None or raw_cant == "":
                        return Response({"error": "cantidad_final es obligatoria"}, status=status.HTTP_400_BAD_REQUEST)
                    try:
                        cantidad = int(raw_cant)
                    except (ValueError, TypeError):
                        return Response({"error": f"cantidad_final inválida: {raw_cant}"}, status=status.HTTP_400_BAD_REQUEST)
                    if cantidad <= 0:
                        return Response({"error": "cantidad_final debe ser > 0"}, status=status.HTTP_400_BAD_REQUEST)

                    raw_desc = item.get("descuento", 0)
                    if raw_desc is None or raw_desc == "":
                        raw_desc = "0"
                    try:
                        descuento = Decimal(str(raw_desc))
                    except (InvalidOperation, ValueError, TypeError):
                        return Response({"error": f"descuento inválido: {raw_desc}"}, status=status.HTTP_400_BAD_REQUEST)

                    try:
                        inventario = Inventario.objects.get(id=inventario_id)
                    except Inventario.DoesNotExist:
                        return Response(
                            {"error": f"Inventario {inventario_id} no encontrado"},
                            status=status.HTTP_404_NOT_FOUND,
                        )

                    if inventario.costo_venta is None:
                        return Response(
                            {"error": f"El producto '{inventario.producto.nombre}' no tiene precio de venta configurado"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    try:
                        precio_unitario_original = Decimal(str(inventario.costo_venta))
                    except (InvalidOperation, ValueError, TypeError) as e:
                        return Response({"error": f"costo_venta inválido para inventario {inventario_id}: {e}"}, status=status.HTTP_400_BAD_REQUEST)

                    stock_ok = inventario.cantidad >= cantidad

                    precio_unitario = precio_unitario_original - (descuento / Decimal(cantidad))
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

                    imagen_url = None
                    if inventario.producto and inventario.producto.imagen:
                        imagen_url = request.build_absolute_uri(inventario.producto.imagen.url)

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
                        "imagen": imagen_url,
                    })

                pedido.subtotal = subtotal
                pedido.gravado_total = gravado_total
                pedido.igv_total = igv_total
                pedido.total = total + costo_envio
                pedido.productos_json = productos_registrados
                import json
                pedido.productos_pedido_json = json.dumps(productos_registrados)
                pedido.save()

            return Response({
                "pedido": {
                    "id": pedido.id,
                    "numero_pedido": pedido.numero_pedido,
                    "tipo_pedido": pedido.tipo_pedido,
                    "canal_venta": pedido.canal_venta,
                    "prioridad": pedido.prioridad,
                    "estado": pedido.estado,
                    "metodo_pago": pedido.metodo_pago,
                    "subtotal": float(pedido.subtotal),
                    "gravado_total": float(pedido.gravado_total),
                    "igv_total": float(pedido.igv_total),
                    "costo_envio": float(pedido.costo_envio),
                    "total": float(pedido.total),
                    "nombre_cliente": pedido.nombre_cliente,
                    "telefono_cliente": pedido.telefono_cliente,
                    "direccion_envio": pedido.direccion_envio,
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


class ListarPedidosView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        page_number = int(request.data.get('page', 1))
        page_size = int(request.data.get('page_size', 5))
        tienda_id = request.user.tienda
        query = request.data.get('query', {})

        pedidos = Pedido.objects.filter(tienda_id=tienda_id)

        from_date = query.get('from_date')
        to_date = query.get('to_date')

        if from_date and to_date:
            tz = timezone.get_current_timezone()
            from_date_obj = make_aware(
                datetime(year=from_date[0], month=from_date[1] + 1, day=from_date[2], hour=0, minute=0, second=0),
                timezone=tz
            )
            to_date_obj = make_aware(
                datetime(year=to_date[0], month=to_date[1] + 1, day=to_date[2], hour=23, minute=59, second=59),
                timezone=tz
            )
            pedidos = pedidos.filter(fecha_hora__range=(from_date_obj, to_date_obj))

        numero_pedido = query.get('numero_pedido')
        metodo_pago = query.get('metodo_pago')
        estado = query.get('estado')
        tipo_pedido = query.get('tipo_pedido')
        canal_venta = query.get('canal_venta')
        estado_pago = query.get('estado_pago')
        prioridad = query.get('prioridad')
        nombre_cliente = query.get('nombre_cliente')
        numero_documento_cliente = query.get('numero_documento_cliente')
        email_cliente = query.get('email_cliente')
        telefono_cliente = query.get('telefono_cliente')
        referencia_externa = query.get('referencia_externa')

        if numero_pedido is not None and numero_pedido != "":
            pedidos = pedidos.filter(numero_pedido__icontains=numero_pedido)
        if metodo_pago is not None and metodo_pago != "":
            pedidos = pedidos.filter(metodo_pago__icontains=metodo_pago)
        if estado is not None and estado != "":
            pedidos = pedidos.filter(estado=estado)
        if tipo_pedido is not None and tipo_pedido != "":
            pedidos = pedidos.filter(tipo_pedido=tipo_pedido)
        if canal_venta is not None and canal_venta != "":
            pedidos = pedidos.filter(canal_venta=canal_venta)
        if estado_pago is not None and estado_pago != "":
            pedidos = pedidos.filter(estado_pago=estado_pago)
        if prioridad is not None and prioridad != "":
            pedidos = pedidos.filter(prioridad=prioridad)
        if nombre_cliente is not None and nombre_cliente != "":
            pedidos = pedidos.filter(nombre_cliente__icontains=nombre_cliente)
        if numero_documento_cliente is not None and numero_documento_cliente != "":
            pedidos = pedidos.filter(numero_documento_cliente__icontains=numero_documento_cliente)
        if email_cliente is not None and email_cliente != "":
            pedidos = pedidos.filter(email_cliente__icontains=email_cliente)
        if telefono_cliente is not None and telefono_cliente != "":
            pedidos = pedidos.filter(telefono_cliente__icontains=telefono_cliente)
        if referencia_externa is not None and referencia_externa != "":
            pedidos = pedidos.filter(referencia_externa__icontains=referencia_externa)

        pedidos = pedidos.order_by('-date_created')

        total_pedidos = pedidos.count()
        total_pages = ceil(total_pedidos / page_size) if page_size > 0 else 0

        next_page = page_number + 1 if page_number < total_pages else None
        previous_page = page_number - 1 if page_number > 1 else None

        start = (page_number - 1) * page_size
        end = start + page_size
        result_page = pedidos[start:end]

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

            import json
            productos_pedido_json_parsed = []
            if pedido.productos_pedido_json:
                try:
                    productos_pedido_json_parsed = json.loads(pedido.productos_pedido_json)
                except (json.JSONDecodeError, TypeError):
                    productos_pedido_json_parsed = []

            pedidos_json.append({
                "id": pedido.id,
                "numero_pedido": pedido.numero_pedido,
                "usuario": pedido.usuario.id if pedido.usuario else None,
                "tienda": pedido.tienda.id if pedido.tienda else None,
                "tipo_pedido": pedido.tipo_pedido,
                "canal_venta": pedido.canal_venta,
                "prioridad": pedido.prioridad,
                "fecha_hora": pedido.fecha_hora.isoformat(),
                "fecha_realizacion": pedido.fecha_realizacion.isoformat() if pedido.fecha_realizacion else None,
                "fecha_vencimiento": pedido.fecha_vencimiento.isoformat() if pedido.fecha_vencimiento else None,
                "fecha_entrega_estimada": pedido.fecha_entrega_estimada.isoformat() if pedido.fecha_entrega_estimada else None,
                "fecha_cancelacion": pedido.fecha_cancelacion.isoformat() if pedido.fecha_cancelacion else None,
                "metodo_pago": pedido.metodo_pago,
                "estado": pedido.estado,
                "estado_pago": pedido.estado_pago,
                "activo": pedido.activo,
                "subtotal": float(pedido.subtotal),
                "gravado_total": float(pedido.gravado_total),
                "igv_total": float(pedido.igv_total),
                "descuento_total": float(pedido.descuento_total),
                "costo_envio": float(pedido.costo_envio),
                "total": float(pedido.total),
                "monto_adelanto": float(pedido.monto_adelanto),
                "metodo_pago_adelanto": pedido.metodo_pago_adelanto,
                "nombre_cliente": pedido.nombre_cliente,
                "numero_documento_cliente": pedido.numero_documento_cliente,
                "email_cliente": pedido.email_cliente,
                "telefono_cliente": pedido.telefono_cliente,
                "direccion_envio": pedido.direccion_envio,
                "referencia_ubicacion": pedido.referencia_ubicacion,
                "observaciones": pedido.observaciones,
                "notas_internas": pedido.notas_internas,
                "motivo_cancelacion": pedido.motivo_cancelacion,
                "referencia_externa": pedido.referencia_externa,
                "productos": productos_json,
                "productos_json": pedido.productos_json,
                "productos_pedido_json": productos_pedido_json_parsed,
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


class ActualizarPedidoView(APIView):
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

            if pedido.estado in ['CANCELADO', 'ENTREGADO']:
                return Response(
                    {"error": f"No se puede editar un pedido {pedido.estado.lower()}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = request.data

            # Actualizar datos del cliente
            cliente_data = data.get('cliente', None)
            if cliente_data:
                if 'tipo_documento' in cliente_data:
                    pedido.tipo_documento_cliente = cliente_data['tipo_documento']
                if 'numero' in cliente_data:
                    pedido.numero_documento_cliente = cliente_data['numero']
                if 'nombre_completo' in cliente_data:
                    pedido.nombre_cliente = cliente_data['nombre_completo']
                if 'correo_cliente' in cliente_data:
                    pedido.email_cliente = cliente_data['correo_cliente']
                if 'telefono_cliente' in cliente_data:
                    pedido.telefono_cliente = cliente_data['telefono_cliente']

            # Actualizar campos simples
            if 'tipo_pedido' in data:
                pedido.tipo_pedido = data['tipo_pedido']
            if 'canal_venta' in data:
                pedido.canal_venta = data['canal_venta']
            if 'prioridad' in data:
                pedido.prioridad = data['prioridad']
            if 'metodo_pago' in data:
                pedido.metodo_pago = data['metodo_pago']
            if 'estado_pago' in data:
                pedido.estado_pago = data['estado_pago']
            if 'monto_adelanto' in data:
                pedido.monto_adelanto = Decimal(str(data['monto_adelanto']))
            if 'metodo_pago_adelanto' in data:
                pedido.metodo_pago_adelanto = data['metodo_pago_adelanto']
            if 'fecha_vencimiento' in data:
                pedido.fecha_vencimiento = data['fecha_vencimiento']
            if 'fecha_entrega_estimada' in data:
                pedido.fecha_entrega_estimada = data['fecha_entrega_estimada']
            if 'observaciones' in data:
                pedido.observaciones = data['observaciones']
            if 'notas_internas' in data:
                pedido.notas_internas = data['notas_internas']
            if 'direccion_envio' in data:
                pedido.direccion_envio = data['direccion_envio']
            if 'referencia_ubicacion' in data:
                pedido.referencia_ubicacion = data['referencia_ubicacion']
            if 'costo_envio' in data:
                pedido.costo_envio = Decimal(str(data['costo_envio']))
            if 'referencia_externa' in data:
                pedido.referencia_externa = data['referencia_externa']

            # Actualizar productos
            productos_data = data.get('productos', None)
            if productos_data is not None:
                with transaction.atomic():
                    # Eliminar productos actuales
                    PedidoProducto.objects.filter(pedido=pedido).delete()

                    subtotal = Decimal("0.00")
                    gravado_total = Decimal("0.00")
                    igv_total = Decimal("0.00")
                    total = Decimal("0.00")
                    productos_registrados = []

                    for item in productos_data:
                        inventario_id = item.get("inventarioId")
                        if inventario_id is None:
                            return Response({"error": "inventarioId es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)
                        raw_cant = item.get("cantidad_final")
                        if raw_cant is None or raw_cant == "":
                            return Response({"error": "cantidad_final es obligatoria"}, status=status.HTTP_400_BAD_REQUEST)
                        try:
                            cantidad = int(raw_cant)
                        except (ValueError, TypeError):
                            return Response({"error": f"cantidad_final inválida: {raw_cant}"}, status=status.HTTP_400_BAD_REQUEST)
                        if cantidad <= 0:
                            return Response({"error": "cantidad_final debe ser > 0"}, status=status.HTTP_400_BAD_REQUEST)
                        raw_desc = item.get("descuento", 0)
                        if raw_desc is None or raw_desc == "":
                            raw_desc = "0"
                        try:
                            descuento = Decimal(str(raw_desc))
                        except (InvalidOperation, ValueError, TypeError):
                            return Response({"error": f"descuento inválido: {raw_desc}"}, status=status.HTTP_400_BAD_REQUEST)

                        try:
                            inventario = Inventario.objects.get(id=inventario_id)
                        except Inventario.DoesNotExist:
                            return Response(
                                {"error": f"Inventario {inventario_id} no encontrado"},
                                status=status.HTTP_404_NOT_FOUND,
                            )

                        if inventario.costo_venta is None:
                            return Response(
                                {"error": f"El producto '{inventario.producto.nombre}' no tiene precio de venta configurado"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        try:
                            precio_unitario_original = Decimal(str(inventario.costo_venta))
                        except (InvalidOperation, ValueError, TypeError) as e:
                            return Response({"error": f"costo_venta inválido para inventario {inventario_id}: {e}"}, status=status.HTTP_400_BAD_REQUEST)

                        stock_ok = inventario.cantidad >= cantidad

                        precio_unitario = precio_unitario_original - (descuento / Decimal(cantidad))
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

                        imagen_url = None
                        if inventario.producto and inventario.producto.imagen:
                            imagen_url = request.build_absolute_uri(inventario.producto.imagen.url)

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
                            "imagen": imagen_url,
                        })

                    pedido.subtotal = subtotal
                    pedido.gravado_total = gravado_total
                    pedido.igv_total = igv_total
                    pedido.total = total + pedido.costo_envio
                    pedido.productos_json = productos_registrados
                    import json
                    pedido.productos_pedido_json = json.dumps(productos_registrados)

            pedido.save()

            # Preparar respuesta con productos actualizados
            productos_finales = PedidoProducto.objects.filter(pedido=pedido)
            productos_json = [
                {
                    "id": p.id,
                    "producto": p.producto.id if p.producto else None,
                    "producto_nombre": p.producto.nombre if p.producto else None,
                    "cantidad": p.cantidad,
                    "valor_unitario": float(p.valor_unitario),
                    "precio_unitario": float(p.precio_unitario),
                    "descuento": float(p.descuento),
                }
                for p in productos_finales
            ]

            return Response({
                "mensaje": "Pedido actualizado exitosamente",
                "pedido": {
                    "id": pedido.id,
                    "numero_pedido": pedido.numero_pedido,
                    "estado": pedido.estado,
                    "tipo_pedido": pedido.tipo_pedido,
                    "canal_venta": pedido.canal_venta,
                    "prioridad": pedido.prioridad,
                    "metodo_pago": pedido.metodo_pago,
                    "estado_pago": pedido.estado_pago,
                    "monto_adelanto": float(pedido.monto_adelanto),
                    "subtotal": float(pedido.subtotal),
                    "igv_total": float(pedido.igv_total),
                    "costo_envio": float(pedido.costo_envio),
                    "total": float(pedido.total),
                    "nombre_cliente": pedido.nombre_cliente,
                    "numero_documento_cliente": pedido.numero_documento_cliente,
                    "telefono_cliente": pedido.telefono_cliente,
                    "direccion_envio": pedido.direccion_envio,
                    "observaciones": pedido.observaciones,
                    "productos": productos_json,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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

            motivo = request.data.get("motivo_cancelacion", "")

            pedido.estado = "CANCELADO"
            pedido.fecha_cancelacion = timezone.now()
            pedido.motivo_cancelacion = motivo
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


class DetallePedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pedido_id):
        try:
            tienda_id = request.user.tienda

            try:
                pedido = Pedido.objects.get(id=pedido_id, tienda_id=tienda_id, activo=True)
            except Pedido.DoesNotExist:
                return Response(
                    {"error": "Pedido no encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )

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

            import json
            productos_pedido_json_parsed = []
            if pedido.productos_pedido_json:
                try:
                    productos_pedido_json_parsed = json.loads(pedido.productos_pedido_json)
                except (json.JSONDecodeError, TypeError):
                    productos_pedido_json_parsed = []

            return Response({
                "id": pedido.id,
                "numero_pedido": pedido.numero_pedido,
                "usuario": pedido.usuario.id if pedido.usuario else None,
                "tienda": pedido.tienda.id if pedido.tienda else None,
                "tipo_pedido": pedido.tipo_pedido,
                "canal_venta": pedido.canal_venta,
                "prioridad": pedido.prioridad,
                "fecha_hora": pedido.fecha_hora.isoformat(),
                "fecha_realizacion": pedido.fecha_realizacion.isoformat() if pedido.fecha_realizacion else None,
                "fecha_vencimiento": pedido.fecha_vencimiento.isoformat() if pedido.fecha_vencimiento else None,
                "fecha_entrega_estimada": pedido.fecha_entrega_estimada.isoformat() if pedido.fecha_entrega_estimada else None,
                "fecha_cancelacion": pedido.fecha_cancelacion.isoformat() if pedido.fecha_cancelacion else None,
                "metodo_pago": pedido.metodo_pago,
                "estado": pedido.estado,
                "estado_pago": pedido.estado_pago,
                "activo": pedido.activo,
                "subtotal": float(pedido.subtotal),
                "gravado_total": float(pedido.gravado_total),
                "igv_total": float(pedido.igv_total),
                "descuento_total": float(pedido.descuento_total),
                "costo_envio": float(pedido.costo_envio),
                "total": float(pedido.total),
                "monto_adelanto": float(pedido.monto_adelanto),
                "metodo_pago_adelanto": pedido.metodo_pago_adelanto,
                "nombre_cliente": pedido.nombre_cliente,
                "numero_documento_cliente": pedido.numero_documento_cliente,
                "email_cliente": pedido.email_cliente,
                "telefono_cliente": pedido.telefono_cliente,
                "direccion_envio": pedido.direccion_envio,
                "referencia_ubicacion": pedido.referencia_ubicacion,
                "observaciones": pedido.observaciones,
                "notas_internas": pedido.notas_internas,
                "motivo_cancelacion": pedido.motivo_cancelacion,
                "referencia_externa": pedido.referencia_externa,
                "productos": productos_json,
                "productos_json": pedido.productos_json,
                "productos_pedido_json": productos_pedido_json_parsed,
                "date_created": pedido.date_created.isoformat() if pedido.date_created else None,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConfirmarEstadoPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    ESTADOS_VALIDOS = ['COTIZADO', 'PENDIENTE', 'CONFIRMADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO']

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

            nuevo_estado = request.data.get('estado')

            if not nuevo_estado:
                return Response(
                    {"error": "El campo 'estado' es obligatorio"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if nuevo_estado not in self.ESTADOS_VALIDOS:
                return Response(
                    {"error": f"Estado no válido. Estados permitidos: {', '.join(self.ESTADOS_VALIDOS)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if pedido.estado == 'CANCELADO':
                return Response(
                    {"error": "No se puede cambiar el estado de un pedido cancelado"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if pedido.estado == 'ENTREGADO':
                return Response(
                    {"error": "No se puede cambiar el estado de un pedido ya entregado"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pedido.estado = nuevo_estado
            pedido.save()

            return Response({
                "mensaje": f"Estado del pedido actualizado a {nuevo_estado}",
                "pedido": {
                    "id": pedido.id,
                    "numero_pedido": pedido.numero_pedido,
                    "estado": pedido.estado,
                    "nombre_cliente": pedido.nombre_cliente,
                    "total": float(pedido.total),
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EliminarPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pedido_id):
        try:
            tienda_id = request.user.tienda

            try:
                pedido = Pedido.objects.get(id=pedido_id, tienda_id=tienda_id)
            except Pedido.DoesNotExist:
                return Response(
                    {"error": "Pedido no encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            numero_pedido = pedido.numero_pedido
            pedido.delete()

            return Response({
                "mensaje": "Pedido eliminado permanentemente.",
                "pedido_id": pedido_id,
                "numero_pedido": numero_pedido
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
