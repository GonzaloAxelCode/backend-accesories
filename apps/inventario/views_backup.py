from sre_parse import State
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
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
User = get_user_model()


class InventarioPagination(PageNumberPagination):
    page_size = 5  # Definir el número de productos por página
    page_size_query_param = 'page_size'  # Opción para que el cliente pueda definir el tamaño de página
    max_page_size = 100  # El tamaño máximo de la página

class CrearInventario(APIView):
    def post(self, request):
        try:
            
            data = request.data
            print(data.get("tienda"))
            producto = get_object_or_404(Producto, id=data.get("producto"))
            tienda = get_object_or_404(Tienda, id=data.get("tienda"))
            proveedor = get_object_or_404(Proveedor, id=data.get("proveedor"))
            user = get_object_or_404(User, id=data.get("responsable"))
            # Verificar si ya existe un inventario con el mismo producto y tienda
            if Inventario.objects.filter(producto=producto, tienda=tienda,proveedor=proveedor).exists():
                return Response(
                    {"message": "Ya existe un inventario con este producto y proveedor para esta tienda.","string_err": "inventario_existente"},
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

class GetAllInventarioAPIView(APIView):
    def get(self, request):
        
        tienda_id = request.user.tienda

       
        inventarios = Inventario.objects.filter(tienda_id=tienda_id)
       

        total_items = inventarios.count()
        page_size = int(request.query_params.get('page_size', 5))
        page_number = int(request.query_params.get('page', 1))
        total_paginas = ceil(total_items / page_size)

        paginator = InventarioPagination()
        paginated_data = paginator.paginate_queryset(inventarios, request)
        serializer = InventarioSerializer(paginated_data, many=True)

        next_page = page_number + 1 if page_number < total_paginas else None
        previous_page = page_number - 1 if page_number > 1 else None

        return Response({
            "count": total_items,
            "next": next_page,
            "previous": previous_page,
            "index_page": page_number - 1,
            "length_pages": total_paginas - 1,
            "results": serializer.data
        })
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


class ObtenerInventarioTienda_____(APIView):
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

class ProductosConMenorStockView(APIView):
    def get(self, request, tienda_id):
        inventarios = (
            Inventario.objects
            .filter(tienda_id=tienda_id)
            .select_related('producto')
            .order_by('cantidad')[:10]
        )

        data = [
            {
                "inventario_id": inv.id, # type: ignore
                "producto_id": inv.producto.id, # type: ignore
                "nombre": inv.producto.nombre,
                "cantidad": inv.cantidad,
            }
            for inv in inventarios
        ]

        return Response({"lowStockProducts":data}, status=status.HTTP_200_OK)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from math import ceil

from apps.inventario.models import Inventario
from apps.inventario.serializers import InventarioSerializer
from apps.producto.models import Producto

class BuscarInventarioAPIView(APIView):
    def post(self, request):
        page_size = int(request.query_params.get('page_size', 5))
        page_number = int(request.query_params.get('page', 1))

        query = request.data.get('query', {})
        nombre = query.get('nombre', "")
        categoria = query.get('categoria', 0)
        tienda = query.get('tienda', 0)
        activo = query.get('activo', None)

        # Si todos los filtros están vacíos
        if not nombre and categoria == 0 and tienda == 0 and activo is None:
            return Response({
                "count": 0,
                "next": None,
                "previous": None,
                "index_page": page_number,
                "length_pages": 0,
                "results": [],
                "search_products_found": "products_not_found"
            }, status=status.HTTP_200_OK)

        inventarios = Inventario.objects.select_related('producto').all()

        # Filtros
        if nombre:
            inventarios = inventarios.filter(producto__nombre__icontains=nombre)
        if categoria and categoria != 0:
            inventarios = inventarios.filter(producto__categoria__id=categoria)
        if tienda and tienda != 0:
            inventarios = inventarios.filter(tienda__id=tienda)
        if activo is not None:
            inventarios = inventarios.filter(activo=activo)

        total_inventarios = inventarios.count()
        

        paginator = InventarioPagination()
        result_page = paginator.paginate_queryset(inventarios, request)
        current_page = paginator.page.number - 1
        total_pages = paginator.page.paginator.num_pages
        next_page = current_page + 1 if paginator.page.has_next() else None
        previous_page = current_page - 1 if paginator.page.has_previous() else None
       

        return Response({
             "count": total_inventarios,
            "next": next_page,
            "previous": previous_page,
            "index_page": current_page,
            "length_pages": total_pages,
            "results": InventarioSerializer(result_page, many=True).data,
            "search_products_found": "products_found" if total_inventarios > 0 else "products_not_found"
        }, status=status.HTTP_200_OK)
