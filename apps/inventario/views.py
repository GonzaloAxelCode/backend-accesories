from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.inventario.models import Inventario
from apps.inventario.serializers import InventarioSerializer
from apps.producto.models import Producto
from apps.proveedor.models import Proveedor
from apps.tienda.models import Tienda

class CrearInventario(APIView):
    def post(self, request):
        try:
            data = request.data
            producto = get_object_or_404(Producto, id=data.get("producto_id"))
            tienda = get_object_or_404(Tienda, id=data.get("tienda_id"))
            

            nuevo_inventario = Inventario.objects.create(
                producto=producto,
                tienda=tienda,
                cantidad=data.get("cantidad", 0),
                stock_minimo=data.get("stock_minimo", 0),
                stock_maximo=data.get("stock_maximo", 100),
                lote=data.get("lote", ""),
                fecha_vencimiento=data.get("fecha_vencimiento"),
                costo=data.get("costo", 0.00),
                
                estado=data.get("estado", "Disponible"),
            )

            serializer = InventarioSerializer(nuevo_inventario)

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class ObtenerInventarioProducto(APIView):
    def get(self, request, producto_id):
        try:
            inventarios = Inventario.objects.filter(producto__id=producto_id)
            if not inventarios.exists():
                return Response({"error": "No hay inventarios para este producto."}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = InventarioSerializer(inventarios, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ObtenerInventarioTienda(APIView):
    def get(self, request, tienda_id):
        try:
            inventarios = Inventario.objects.filter(tienda__id=tienda_id)
            if not inventarios.exists():
                return Response({"error": "No hay inventarios para esta tienda."}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = InventarioSerializer(inventarios, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ActualizarStock(APIView):
    def patch(self, request, inventario_id):
        try:
            inventario = get_object_or_404(Inventario, id=inventario_id)
            cantidad_nueva = request.data.get("cantidad", 0)

            if not isinstance(cantidad_nueva, int) or cantidad_nueva <= 0:
                return Response({"error": "La cantidad debe ser un número entero positivo."}, status=status.HTTP_400_BAD_REQUEST)

            nuevo_stock = inventario.cantidad + cantidad_nueva

            if nuevo_stock > inventario.stock_maximo:
                return Response({"error": "No se puede superar el stock máximo permitido."}, status=status.HTTP_400_BAD_REQUEST)

            inventario.cantidad = nuevo_stock
            inventario.save()

            return Response({"message": "Stock actualizado correctamente.", "nuevo_stock": inventario.cantidad}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AjustarStock(APIView):
    def patch(self, request, inventario_id):
        try:
            inventario = get_object_or_404(Inventario, id=inventario_id)
            cantidad_ajuste = request.data.get("cantidad", 0)

            if not isinstance(cantidad_ajuste, int):
                return Response({"error": "La cantidad debe ser un número entero."}, status=status.HTTP_400_BAD_REQUEST)

            nuevo_stock = inventario.cantidad + cantidad_ajuste

            if nuevo_stock < 0:
                return Response({"error": "No se puede tener stock negativo."}, status=status.HTTP_400_BAD_REQUEST)

            if nuevo_stock > inventario.stock_maximo:
                return Response({"error": "El stock no puede superar el máximo permitido."}, status=status.HTTP_400_BAD_REQUEST)

            inventario.cantidad = nuevo_stock
            inventario.save()

            return Response({"message": "Stock ajustado correctamente.", "nuevo_stock": inventario.cantidad}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerificarStock(APIView):
    def get(self, request, inventario_id):
        try:
            inventario = get_object_or_404(Inventario, id=inventario_id)

            stock_status = "Stock en nivel adecuado"
            if inventario.cantidad < inventario.stock_minimo:
                stock_status = "Stock bajo el mínimo permitido"
            elif inventario.cantidad == 0:
                stock_status = "Producto agotado"

            stock_info = {
                "producto": inventario.producto.nombre,
                "tienda": inventario.tienda.nombre,
                "stock_actual": inventario.cantidad,
                "stock_minimo": inventario.stock_minimo,
                "stock_maximo": inventario.stock_maximo,
                "estado": stock_status
            }

            return Response(stock_info, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )