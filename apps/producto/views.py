import json
from math import ceil, prod
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.inventario.models import Inventario
from apps.producto.models import Producto
from apps.producto.serializers import ProductoSerializer
from django.db.models import Q

from django.db.models import Q
import re

from django.db.models import Q
import re

from rest_framework.parsers import MultiPartParser, FormParser


from django.db.models import Q
import re
from rest_framework.permissions import IsAuthenticated

from core.permissions import CanCreateProductPermission, CanDeleteProductPermission, CanUpdateProductPermission

class ProductoPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class BuscarProductoAPIView(APIView):
    permission_classes = [IsAuthenticated]
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

    

        # ----- Query -----
        productos = Producto.objects.filter(filtros,activo=True).distinct()
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
class GetAllProductosAPIViewWithPagination(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Solo productos activos
        productos = Producto.objects.filter(tienda=tienda).exclude(nombre__icontains="(Delete)")
        total_productos = productos.count()
        page_size = int(request.query_params.get('page_size', 10))
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
            "length_pages": total_paginas ,
            "results": serializer.data,
            
        })



class GetAllProductosAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."},
                            status=status.HTTP_400_BAD_REQUEST)

        
        serializer_all = ProductoSerializer(Producto.objects.filter(tienda=tienda,activo=True), many=True)
       

        return Response({
           
            "results":serializer_all.data
        })


# ---------- OBTENER UN SOLO PRODUCTO ----------
class GetProductoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda,activo=True)
        serializer = ProductoSerializer(producto)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class CreateProductoAPIView(APIView):
    permission_classes = [IsAuthenticated, CanCreateProductPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        data = request.data.copy()

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "Usuario sin tienda asignada"}, status=400)

        # -------------------------------
        # Convertir caracteristicas JSON string → dict
        # -------------------------------
        caracteristicas_raw = data.get("caracteristicas")

        if caracteristicas_raw:
            try:
                data["caracteristicas"] = json.loads(caracteristicas_raw)
            except Exception:
                return Response(
                    {"caracteristicas": ["El valor debe ser JSON válido."]},
                    status=400
                )
        else:
            data["caracteristicas"] = {}

        # ⚠️ Aquí está la solución clave
        data = data.dict()

        # -------------------------------
        # Serializar
        # -------------------------------
        serializer = ProductoSerializer(data=data)

        if serializer.is_valid():
            producto = serializer.save(tienda=tienda, activo=True)

            Inventario.objects.create(
                responsable=request.user,
                producto=producto,
                tienda=tienda,
                descripcion="Descripción",
                cantidad=1,
                stock_minimo=1,
                stock_maximo=15000,
                costo_compra=0.00,
                costo_venta=0.00,
                costo=0.00,
                estado="Disponible"
            )

            return Response({
                "message": "Producto e inventario creado exitosamente",
                "producto": serializer.data
            }, status=201)

        return Response(serializer.errors, status=400)



class UpdateProductoAPIView(APIView):
    permission_classes = [IsAuthenticated, CanUpdateProductPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)

        data = request.data.copy()

        # ------------------------------------
        # Convertir JSON string → dict (OBLIGATORIO)
        # ------------------------------------
        caracteristicas_raw = data.get("caracteristicas")

        if caracteristicas_raw is not None:
            try:
                data["caracteristicas"] = json.loads(caracteristicas_raw)
            except Exception:
                return Response(
                    {"caracteristicas": ["El valor debe ser JSON válido."]},
                    status=400
                )

        # Convertir QueryDict a dict normal
        data = data.dict()

        # ------------------------------------
        # Serializar actualización completa o parcial
        # ------------------------------------
        serializer = ProductoSerializer(producto, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Producto actualizado exitosamente",
                    "producto": serializer.data
                },
                status=200
            )

        return Response(serializer.errors, status=400)



# ---------- ELIMINAR PRODUCTO ----------
class DeleteProductoAPIView(APIView):
    permission_classes = [IsAuthenticated,CanDeleteProductPermission]
    def delete(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)
        producto.activo = False
        producto.categoria = None
        producto.nombre = f"{producto.nombre}(Delete)"
        
        producto.save()
        Inventario.objects.filter(producto=producto, tienda=tienda).update(activo=False)
 
        return Response({
            "message": "Producto eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)
