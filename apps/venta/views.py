from datetime import timedelta
import datetime
from django.shortcuts import render
from django.db.models import Sum

# Create your views here.
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.urls import path
from django.contrib.auth import get_user_model
from decimal import Decimal

from apps.venta.serialzers import VentaSerializer,DetalleVentaSerializer
from core import settings
from .models import Venta, DetalleVenta
from apps.producto.models import Producto
from apps.cliente.models import Cliente
from apps.tienda.models import Tienda
from django.utils.timezone import now




User = get_user_model()

class CrearVenta(APIView):
    def post(self, request):
        data = request.data
        
        print(data)

        # Obtener objetos relacionados
        cliente = get_object_or_404(Cliente, id=data.get("cliente"))
        usuario = get_object_or_404(User, id=data.get("usuario"))
        tienda = get_object_or_404(Tienda, id=data.get("tienda"))

        # Crear la venta
        venta = Venta.objects.create(
            cliente=cliente,
            usuario=usuario,
            tienda=tienda,
            metodo_pago=data.get("metodo_pago"),
            estado=data.get("estado", "Completada"),
            tipo_comprobante=data.get("tipo_comprobante"),
            serie=data.get("serie"),
            numero=data.get("numero"),
            ruc_empresa=data.get("ruc_empresa"),
            razon_social=data.get("razon_social"),
            direccion_empresa=data.get("direccion_empresa"),
            documento_cliente=data.get("documento_cliente"),
            condicion_venta=data.get("condicion_venta"),
            total_gravado=0,
            igv=0,
            total=0
        )

        total_gravado = 0
        igv_total = 0
        total_venta = 0

        # Crear los detalles de la venta
        for detalle in data.get("detalles", []):
            producto = get_object_or_404(Producto, id=detalle["producto"])
            subtotal = detalle["cantidad"] * detalle["precio_unitario"]
            impuestos = detalle.get("impuestos", 0)
            
            DetalleVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=detalle["cantidad"],
                precio_unitario=detalle["precio_unitario"],
                subtotal=subtotal,
                descuento=detalle.get("descuento", 0),
                impuestos=impuestos,
                notas=detalle.get("notas", "")
            )

            total_gravado += subtotal
            igv_total += impuestos
            total_venta += subtotal + impuestos

        # Actualizar los totales en la venta
        venta.total_gravado = total_gravado
        venta.igv = igv_total
        venta.total = total_venta # type: ignore
        venta.save()
        venta_serializada = VentaSerializer(venta)
        return Response({"mensaje": "Venta creada exitosamente", "venta": venta_serializada.data}, status=status.HTTP_201_CREATED)

        

class VentasPorTienda(APIView):
    def get(self, request, tienda_id):
        if not tienda_id:
            return Response({"error": "Debe seleccionar una tienda."}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas en esta tienda."}, status=status.HTTP_200_OK)

        ventas_data = []
        for venta in ventas:
            venta_serializada = VentaSerializer(venta).data
            detalles = DetalleVenta.objects.filter(venta=venta)
            detalles_serializados = DetalleVentaSerializer(detalles, many=True).data
            venta_serializada["detalles"] = detalles_serializados  # Agregamos los detalles a la venta
            ventas_data.append(venta_serializada)

        return Response(ventas_data, status=status.HTTP_200_OK)
