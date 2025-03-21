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

from django.contrib.auth import get_user_model
User = get_user_model()
class CrearInventario(APIView):
    def post(self, request):
        try:
            data = request.data
            producto = get_object_or_404(Producto, id=data.get("producto"))
            tienda = get_object_or_404(Tienda, id=data.get("tienda"))
            proveedor = get_object_or_404(Proveedor, id=data.get("proveedor"))
            user = get_object_or_404(User, id=data.get("responsable"))
            # Verificar si ya existe un inventario con el mismo producto y tienda
            if Inventario.objects.filter(producto=producto, tienda=tienda).exists():
                return Response(
                    {"message": "Ya existe un inventario con este producto en esta tienda.","string_err": "inventario_existente"},
                    status=status.HTTP_400_BAD_REQUEST
                ) 

            nuevo_inventario = Inventario.objects.create(
                responsable=user,
                proveedor=proveedor,
                descripcion=data.get("descripcion",""),
                producto=producto,
                tienda=tienda,
                cantidad=data.get("cantidad", 0),
                stock_minimo=data.get("stock_minimo", 0),
                stock_maximo=data.get("stock_maximo", 100),
                costo_compra=data.get("costo_compra", 0.00),
                costo_venta=data.get("costo_venta", 0.00),
                costo=data.get("costo_compra", 0.00),
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


class ActualizarInventarioView(APIView):
    def patch(self, request, *args, **kwargs):
        try:
            inventario_id = request.data.get("id")
            nuevo_stock = request.data.get("cantidad")
            nuevo_costo_compra = request.data.get("costo_compra")
            nuevo_costo_venta = request.data.get("costo_venta")

            if not inventario_id:
                return Response({"error": "inventario_id es requerido"}, status=status.HTTP_400_BAD_REQUEST)

            inventario = get_object_or_404(Inventario, id=inventario_id)

            # Validar stock mínimo y máximo
            if nuevo_stock is not None:
                if nuevo_stock < inventario.stock_minimo:
                    return Response({"error": f"El stock no puede ser menor a {inventario.stock_minimo}"}, status=status.HTTP_400_BAD_REQUEST)
                if nuevo_stock > inventario.stock_maximo:
                    return Response({"error": f"El stock no puede ser mayor a {inventario.stock_maximo}"}, status=status.HTTP_400_BAD_REQUEST)
                inventario.cantidad = nuevo_stock  # Actualizar stock solo si está dentro del rango

            # Actualizar costos si fueron proporcionados
            if nuevo_costo_compra is not None:
                inventario.costo_compra = nuevo_costo_compra
            if nuevo_costo_venta is not None:
                inventario.costo_venta = nuevo_costo_venta

            # Guardar cambios en la base de datos
            inventario.save()

            return Response(InventarioSerializer(inventario).data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Error al actualizar inventario: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class EliminarInventario(APIView):
   def delete(self, request, inventario_id):
        inventario = get_object_or_404(Inventario, id=inventario_id) 
        inventario.delete()
        return Response({"message": "Inventario eliminado exitosamente"}, status=status.HTTP_200_OK)

        
 
    
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
