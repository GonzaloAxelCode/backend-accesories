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

from apps.venta.serialzers import VentaSerializer
from core import settings
from .models import Venta, DetalleVenta
from apps.producto.models import Producto
from apps.cliente.models import Cliente
from apps.tienda.models import Tienda


User = get_user_model()


from django.utils.timezone import now

# Crear una venta
class CrearVenta(APIView):
    def post(self, request):
        try:
            data = request.data
            cliente = get_object_or_404(Cliente, id=data['cliente'])
            usuario = get_object_or_404(User, id=data['usuario']) # type: ignore
            tienda = get_object_or_404(Tienda, id=data['tienda'])
            productos = data['productos']  # Lista de productos vendidos
            
            total = 0
            detalles = []

            for item in productos:
                producto = get_object_or_404(Producto, id=item['producto'])
                cantidad = item['cantidad']
                precio_unitario = producto.precio
                subtotal = Decimal(cantidad) * Decimal(precio_unitario)
                descuento = Decimal(item.get('descuento', 0))
                impuestos = (subtotal - descuento) * Decimal('0.18')
                total += subtotal - descuento + impuestos
                
                detalles.append(DetalleVenta(
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal,
                    descuento=descuento,
                    impuestos=impuestos
                ))
            
            venta = Venta.objects.create(
                cliente=cliente,
                usuario=usuario,
                tienda=tienda,
                total=total,
                metodo_pago=data['metodo_pago'],
                estado='Completada',
                descuento=sum(d.descuento for d in detalles),
                impuestos=sum(d.impuestos for d in detalles),
                factura=data.get('factura', ''),
                fecha_realizacion=now()
            )
            
            for detalle in detalles:
                detalle.venta = venta
                detalle.save()
            
            return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Cancelar una venta
class CancelarVenta(APIView):
    def patch(self, request, id):
        venta = get_object_or_404(Venta, id=id)
        if venta.estado == "Cancelada":
            return Response({"message": "La venta ya está cancelada."}, status=status.HTTP_400_BAD_REQUEST)
        
        venta.estado = "Cancelada"
        venta.fecha_cancelacion = now()
        venta.save()
        return Response({"message": "Venta cancelada correctamente."}, status=status.HTTP_200_OK)

from django.db.models import Q

class ListarVentas(APIView):
    def get(self, request):
        filtro = request.query_params.get('filtro', 'hoy')
        tienda_id = request.query_params.get('tienda', None)
        estado = request.query_params.get('estado', None)  # Filtro por estado de la venta
        fecha_inicio = request.query_params.get('fecha_inicio', None)  # Filtro por fecha de inicio
        fecha_fin = request.query_params.get('fecha_fin', None)  # Filtro por fecha de fin
        cliente_id = request.query_params.get('cliente', None)  # Filtro por cliente
        producto_id = request.query_params.get('producto', None)  # Filtro por producto
        
        ventas = Venta.objects.all()
        
        if filtro == 'hoy':
            ventas = ventas.filter(fecha_realizacion__date=now().date())
        elif filtro == 'semana':
            ventas = ventas.filter(fecha_realizacion__gte=now() - timedelta(days=7))
        elif filtro == 'mes':
            ventas = ventas.filter(fecha_realizacion__month=now().month, fecha_realizacion__year=now().year)
        elif filtro == 'ultimos3dias':
            ventas = ventas.filter(fecha_realizacion__gte=now() - timedelta(days=3))
        
        if tienda_id:
            ventas = ventas.filter(tienda_id=tienda_id)
        
        if estado:
            ventas = ventas.filter(estado=estado)
        
        if fecha_inicio:
            ventas = ventas.filter(fecha_realizacion__gte=fecha_inicio)
        
        if fecha_fin:
            ventas = ventas.filter(fecha_realizacion__lte=fecha_fin)
        
        if cliente_id:
            ventas = ventas.filter(cliente_id=cliente_id)
        
        if producto_id:
            # Filtrar por productos dentro de los detalles de la venta
            ventas = ventas.filter(detalles__producto_id=producto_id)
        
        # Si quieres también incluir productos y clientes en los filtros, puedes hacer un filtro adicional por sus modelos.
        # Por ejemplo, puedes utilizar `Q` para realizar búsquedas complejas.
        if cliente_id or producto_id:
            ventas = ventas.filter(Q(cliente_id=cliente_id) | Q(detalles__producto_id=producto_id))

        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Función auxiliar para verificar la tienda
def verificar_tienda(request):
    tienda_id = request.query_params.get('tienda', None)
    if not tienda_id:
        return None, "Debe seleccionar una tienda."
    return tienda_id, None

# 1. Obtener las ventas de hoy
class VentasHoy(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        
        ventas = Venta.objects.filter(fecha_realizacion__date=now().date(), tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas hoy en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 2. Obtener ventas por cliente
class VentasPorCliente(APIView):
    def get(self, request, cliente_id):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        
        ventas = Venta.objects.filter(cliente_id=cliente_id, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas para este cliente en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 3. Obtener productos más vendidos
class ProductosMasVendidos(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        
        productos_vendidos = DetalleVenta.objects.filter(venta__tienda_id=tienda_id).values('producto').annotate(total_vendido=Sum('cantidad')).order_by('-total_vendido')
        if not productos_vendidos:
            return Response({"message": "No hay productos vendidos en esta tienda."}, status=status.HTTP_200_OK)
        
        productos = [{'producto': Producto.objects.get(id=item['producto']).nombre, 'total_vendido': item['total_vendido']} for item in productos_vendidos]
        return Response(productos, status=status.HTTP_200_OK)

# 4. Obtener ventas por tienda
class VentasPorTienda(APIView):
    def get(self, request, tienda_id):
        if not tienda_id:
            return Response({"error": "Debe seleccionar una tienda."}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas en esta tienda."}, status=status.HTTP_200_OK)

        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 5. Obtener total de ventas por día
class TotalVentasPorDia(APIView):
    def get(self, request, fecha):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d") # type: ignore
        ventas = Venta.objects.filter(fecha_realizacion__date=fecha_obj, tienda_id=tienda_id)
        total_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
        if total_ventas == 0:
            return Response({"message": "No hay ventas en esta tienda para la fecha seleccionada."}, status=status.HTTP_200_OK)
        
        return Response({"fecha": fecha, "total_ventas": total_ventas}, status=status.HTTP_200_OK)

# 6. Obtener ventas por método de pago
class VentasPorMetodoPago(APIView):
    def get(self, request, metodo_pago):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(metodo_pago=metodo_pago, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas con este método de pago en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 7. Obtener el total de impuestos de las ventas
class TotalImpuestosVentas(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(tienda_id=tienda_id)
        total_impuestos = ventas.aggregate(total_impuestos=Sum('impuestos'))['total_impuestos'] or 0
        return Response({"total_impuestos": total_impuestos}, status=status.HTTP_200_OK)

# 8. Obtener ventas pendientes de cancelación
class VentasPendientesCancelacion(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(estado='Completada', tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas pendientes de cancelación en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 9. Obtener ventas en un rango de fechas
class VentasPorRangoFechas(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        ventas = Venta.objects.filter(fecha_realizacion__range=[fecha_inicio, fecha_fin], tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas en el rango de fechas seleccionado para esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 10. Obtener ventas por estado de entrega
class VentasPorEstado(APIView):
    def get(self, request, estado):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(estado=estado, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas con este estado de entrega en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 11. Ver el detalle de una venta con productos asociados
class DetalleVentaConProductos(APIView):
    def get(self, request, id):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        venta = get_object_or_404(Venta, id=id, tienda_id=tienda_id)
        detalles_venta = DetalleVenta.objects.filter(venta=venta)
        detalles = [{'producto': detalle.producto.nombre, 'cantidad': detalle.cantidad, 'precio_unitario': detalle.precio_unitario, 'subtotal': detalle.subtotal} for detalle in detalles_venta] # type: ignore
        return Response({'venta_id': venta.id, 'detalles': detalles}, status=status.HTTP_200_OK) # type: ignore

# 12. Obtener las ventas de la semana
class VentasSemana(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(fecha_realizacion__gte=now() - timedelta(days=7), tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas esta semana en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 13. Obtener ventas del mes
class VentasMes(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(fecha_realizacion__month=now().month, fecha_realizacion__year=now().year, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas este mes en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 14. Obtener ventas de los últimos 3 días
class VentasUltimos3Dias(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(fecha_realizacion__gte=now() - timedelta(days=3), tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas en los últimos 3 días en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 15. Obtener ventas por tipo de cliente
class VentasPorTipoCliente(APIView):
    def get(self, request, tipo_cliente):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(cliente__tipo_cliente=tipo_cliente, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas de este tipo de cliente en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 16. Obtener ventas por producto específico
class VentasPorProducto(APIView):
    def get(self, request, producto_id):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(detalleventa__producto_id=producto_id, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas de este producto en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 17. Obtener el total de ventas de todos los productos vendidos
class TotalVentasPorProducto(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = DetalleVenta.objects.filter(venta__tienda_id=tienda_id).values('producto').annotate(total_ventas=Sum('subtotal')).order_by('-total_ventas')
        if not ventas:
            return Response({"message": "No hay ventas de productos en esta tienda."}, status=status.HTTP_200_OK)

        return Response(ventas, status=status.HTTP_200_OK)

# 18. Obtener ventas por rango de precios
class VentasPorRangoPrecios(APIView):
    def get(self, request):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        precio_min = float(request.query_params.get('precio_min', 0))
        precio_max = float(request.query_params.get('precio_max', 999999))
        ventas = Venta.objects.filter(total__range=[precio_min, precio_max], tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas en el rango de precios seleccionado."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 19. Obtener ventas por estado de pago
class VentasPorEstadoPago(APIView):
    def get(self, request, estado_pago):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(estado_pago=estado_pago, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas con este estado de pago en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 20. Obtener ventas por vendedor
class VentasPorVendedor(APIView):
    def get(self, request, vendedor_id):
        tienda_id, error = verificar_tienda(request)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        ventas = Venta.objects.filter(vendedor_id=vendedor_id, tienda_id=tienda_id)
        if not ventas.exists():
            return Response({"message": "No hay ventas de este vendedor en esta tienda."}, status=status.HTTP_200_OK)
        
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




# Obtener detalles de una venta
class ObtenerVenta(APIView):
    def get(self, request, id):
        venta = get_object_or_404(Venta, id=id)
        serializer = VentaSerializer(venta)
        return Response(serializer.data, status=status.HTTP_200_OK)


