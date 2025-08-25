from math import ceil
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.producto.models import Producto
from apps.producto.serializers import ProductoSerializer


# ---------- PAGINACIÓN ----------
class ProductoPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------- BUSCAR PRODUCTOS ----------
class BuscarProductoAPIView(APIView):
    def post(self, request):
        query = request.data.get('query', {})

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."},
                            status=status.HTTP_400_BAD_REQUEST)

        nombre = query.get('nombre', "")
        categoria = query.get('categoria', 0)
        activo = query.get('activo', None)

        productos = Producto.objects.filter(tienda=tienda)

        if nombre:
            productos = productos.filter(nombre__icontains=nombre)
        if categoria and categoria != 0:
            productos = productos.filter(categoria__id=categoria)
        if activo is not None:
            productos = productos.filter(activo=activo)

        total_productos = productos.count()

        # Paginación
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


# ---------- LISTAR TODOS LOS PRODUCTOS ----------
class GetAllProductosAPIView(APIView):
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."},
                            status=status.HTTP_400_BAD_REQUEST)

        productos = Producto.objects.filter(tienda=tienda).order_by('id')
        total_productos = productos.count()

        page_size = int(request.query_params.get('page_size', 5))
        page_number = int(request.query_params.get('page', 1))
        total_paginas = ceil(total_productos / page_size)

        # Paginación
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


# ---------- OBTENER UN SOLO PRODUCTO ----------
class GetProductoAPIView(APIView):
    def get(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)
        serializer = ProductoSerializer(producto)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------- CREAR UN PRODUCTO ----------
class CreateProductoAPIView(APIView):
    def post(self, request):
        data = request.data
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Verificar duplicados
        if Producto.objects.filter(tienda=tienda, nombre=data.get("nombre")).exists():
            return Response(
                {"error": "Ya existe un producto con ese nombre en tu tienda."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Producto.objects.filter(tienda=tienda, descripcion=data.get("descripcion")).exists():
            return Response(
                {"error": "Ya existe un producto con esa descripción en tu tienda."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProductoSerializer(data=data)
        if serializer.is_valid():
            serializer.save(tienda=tienda)
            return Response({
                "message": "Producto creado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------- ACTUALIZAR PRODUCTO ----------
class UpdateProductoAPIView(APIView):
    def put(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)

        serializer = ProductoSerializer(producto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Producto actualizado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------- ELIMINAR PRODUCTO ----------
class DeleteProductoAPIView(APIView):
    def delete(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)
        producto.delete()
        return Response({
            "message": "Producto eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)
