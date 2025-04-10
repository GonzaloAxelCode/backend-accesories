from math import ceil
from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Producto
from .serializers import ProductoSerializer
from rest_framework.pagination import PageNumberPagination


class ProductoPagination(PageNumberPagination):
    page_size = 5  # Definir el número de productos por página
    page_size_query_param = 'page_size'  # Opción para que el cliente pueda definir el tamaño de página
    max_page_size = 100  # El tamaño máximo de la página


class BuscarProductoAPIView(APIView):
    def post(self, request):
        query = request.data.get('query', {})
        nombre = query.get('nombre', "")
        categoria = query.get('categoria', 0)
        activo = query.get('activo', None)

        if not nombre and categoria == 0 and activo is None:
            return Response({
                "count": 0,
                "next": None,
                "previous": None,
                "index_page": 0,
                "length_pages": 0,
                "results": [],
                "search_products_found": "products_not_found"
            })

        # Filtrar productos
        productos = Producto.objects.all()
        if nombre:
            productos = productos.filter(nombre__icontains=nombre)
        if categoria and categoria != 0:
            productos = productos.filter(categoria__id=categoria)
        if activo is not None:
            productos = productos.filter(activo=activo)

        total_productos = productos.count()

        # Aplicar paginación
        paginator = ProductoPagination()
        result_page = paginator.paginate_queryset(productos, request)

        current_page = paginator.page.number - 1
        total_pages = paginator.page.paginator.num_pages
        next_page = current_page + 1 if paginator.page.has_next() else None
        previous_page = current_page - 1 if paginator.page.has_previous() else None

        return Response({
            "count": total_productos,
            "next": next_page,
            "previous": previous_page,
            "index_page": current_page,
            "length_pages": total_pages,
            "results": ProductoSerializer(result_page, many=True).data,
            "search_products_found": "products_found" if total_productos > 0 else "products_not_found"
        })
        
        
class GetAllProductosAPIView(APIView):
    def get(self, request):
            productos = Producto.objects.all()
            total_productos = productos.count()
            page_size = int(request.query_params.get('page_size', 5))
            page_number = int(request.query_params.get('page', 1))
            total_paginas = ceil(total_productos / page_size)

            paginator = ProductoPagination()
            paginated_products = paginator.paginate_queryset(productos, request)
            serializer = ProductoSerializer(paginated_products, many=True)

            next_page = page_number + 1 if page_number < total_paginas else None
            previous_page = page_number - 1 if page_number > 1 else None

            return Response({
                "count": total_productos,
                "next": next_page,
                "previous": previous_page,
                "index_page": page_number - 1,
                "length_pages": total_paginas - 1,
                "results": serializer.data
            })
# Obtener todos los productos
class GetAllProductosAPIView___(APIView):
    def get(self, request):
        productos = Producto.objects.all()
        serializer = ProductoSerializer(productos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



        
        
# Obtener un solo producto
class GetProductoAPIView(APIView):
    def get(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        serializer = ProductoSerializer(producto)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Crear un nuevo producto
class CreateProductoAPIView(APIView):
    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Producto creado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Actualizar un producto
class UpdateProductoAPIView(APIView):
    def put(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        serializer = ProductoSerializer(producto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Producto actualizado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Eliminar un producto
class DeleteProductoAPIView(APIView):
    def delete(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        producto.delete()
        return Response({
            "message": "Producto eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)


