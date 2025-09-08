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



from django.db.models import Q

from django.db.models import Q
import re

from django.db.models import Q
import re



from django.db.models import Q
import re

class BuscarProductoAPIView(APIView):
    def post(self, request):
        data = request.data
        query = data.get("query", data)  # soporta {query:{}} o plano

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----- Parámetros -----
        nombre = (query.get('nombre') or "").strip().lower()
        nombre_normalizado = re.sub(r"\s+", " ", nombre).strip()

        sku = (query.get('sku') or "").strip()  # 🚨 nuevo campo SKU

        categoria = query.get('categoria') or 0
        try:
            categoria = int(categoria)
        except (ValueError, TypeError):
            categoria = 0

        activo = query.get('activo', None)

        # ----- Filtros -----
        filtros = Q(tienda=tienda)

        if sku:  # 🔎 búsqueda exacta por SKU
            filtros &= Q(sku__iexact=sku)

        if nombre_normalizado:
            palabras = nombre_normalizado.split(" ")
            for palabra in palabras:
                filtros &= Q(nombre__icontains=palabra) | Q(descripcion__icontains=palabra)

        if categoria > 0:
            filtros &= Q(categoria_id=categoria)

        if activo is not None:
            filtros &= Q(activo=activo)

        # ----- Query -----
        productos = Producto.objects.filter(filtros).distinct()
        total_productos = productos.count()

        if total_productos == 0:
            return Response({
                "count": 0,
                "next": None,
                "previous": None,
                "index_page": 1,
                "length_pages": 0,
                "results": [],
                "search_products_found": "products_not_found"
            })

        # ----- Paginación -----
        paginator = ProductoPagination()
        result_page = paginator.paginate_queryset(productos, request)

        return Response({
            "count": total_productos,
            "next": paginator.page.next_page_number() if paginator.page.has_next() else None,
            "previous": paginator.page.previous_page_number() if paginator.page.has_previous() else None,
            "index_page": paginator.page.number - 1,
            "length_pages": paginator.page.paginator.num_pages -1,
            "results": ProductoSerializer(result_page, many=True).data,
            "search_products_found": "products_found"
        })


# ---------- LISTAR TODOS LOS PRODUCTOS ----------
class GetAllProductosAPIView(APIView):
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."},
                            status=status.HTTP_400_BAD_REQUEST)

        productos = Producto.objects.filter(tienda=tienda).order_by('id')
        serializer_all = ProductoSerializer(Producto.objects.filter(tienda=tienda).order_by('id'), many=True)
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
            "results": serializer.data,
            "all_results":serializer_all.data
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
