from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from math import ceil
import re
from django.db.models import Q

from django.contrib.auth import get_user_model
from apps.inventario.models import Inventario
from apps.inventario.serializers import InventarioSerializer
from apps.producto.models import Producto
from apps.producto.serializers import ProductoSerializer
from apps.proveedor.models import Proveedor

User = get_user_model()


# ---------- PAGINACIÓN ----------
class InventarioPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------- CREAR INVENTARIO ----------
class CrearInventario(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request):
        try:
            data = request.data
            tienda = getattr(request.user, "tienda", None)
            if not tienda:
                return Response({"error": "El usuario no tiene una tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)

            producto = get_object_or_404(Producto, id=data.get("producto"))
            proveedor = get_object_or_404(Proveedor, id=data.get("proveedor"))
            user = request.user

            if Inventario.objects.filter(producto=producto, tienda=tienda, proveedor=proveedor).exists():
                return Response(
                    {"message": "Ya existe un inventario con este producto y proveedor para esta tienda.",
                     "string_err": "inventario_existente"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            nuevo_inventario = Inventario.objects.create(
                responsable=user,
                proveedor=proveedor,
                descripcion=data.get("descripcion", ""),
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
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetAllInventarioAPIView(APIView):
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = Inventario.objects.filter(tienda=tienda)
        
        
        serializer = InventarioSerializer(qs, many=True)    


        return Response({
            
            "results": serializer.data
        })

class GetAllInventarioAPIViewWithpagination(APIView):
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = Inventario.objects.filter(tienda=tienda)
        paginator = InventarioPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = InventarioSerializer(page, many=True)    


        pg = paginator.page  # objeto de paginación real de DRF

        # --- respuesta personalizada ---
        print({
            "count": pg.paginator.count,
            "next": pg.next_page_number() if pg.has_next() else None,
            "previous": pg.previous_page_number() if pg.has_previous() else None,
           "index_page": pg.number ,  # 👈 base 0 para frontend
            "length_pages": pg.paginator.num_pages,  # 👈 también base 0
            "results": serializer.data
        })
        return Response({
            "count": pg.paginator.count,
            "next": pg.next_page_number()  if pg.has_next()   else None,
            "previous": pg.previous_page_number() if pg.has_previous() else None,
           "index_page": pg.number ,  # 👈 base 0 para frontend
            "length_pages": pg.paginator.num_pages  , # 👈 también base 0
            "results": serializer.data
        })


# ---------- INVENTARIO POR PRODUCTO ----------
class ObtenerInventarioProducto(APIView):
    def get(self, request, producto_id):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asociada."}, status=status.HTTP_400_BAD_REQUEST)

        inventarios = Inventario.objects.filter(producto__id=producto_id, tienda=tienda)
        if not inventarios.exists():
            return Response({"error": "No hay inventarios para este producto en tu tienda."}, status=status.HTTP_404_NOT_FOUND)

        serializer = InventarioSerializer(inventarios, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------- ACTUALIZAR STOCK ----------
class ActualizarStock(APIView):
    def patch(self, request, inventario_id):
        try:
            tienda = getattr(request.user, "tienda", None)
            inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)

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


# ---------- ACTUALIZAR INVENTARIO ----------
class ActualizarInventarioView(APIView):
    def patch(self, request, *args, **kwargs):
        try:
            tienda = getattr(request.user, "tienda", None)
            inventario_id = request.data.get("id")
            if not inventario_id:
                return Response({"error": "inventario_id es requerido"}, status=status.HTTP_400_BAD_REQUEST)

            inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)

            nuevo_stock = request.data.get("cantidad")
            nuevo_costo_compra = request.data.get("costo_compra")
            nuevo_costo_venta = request.data.get("costo_venta")

            if nuevo_stock is not None:
                if nuevo_stock < inventario.stock_minimo:
                    return Response({"error": f"El stock no puede ser menor a {inventario.stock_minimo}"}, status=status.HTTP_400_BAD_REQUEST)
                if nuevo_stock > inventario.stock_maximo:
                    return Response({"error": f"El stock no puede ser mayor a {inventario.stock_maximo}"}, status=status.HTTP_400_BAD_REQUEST)
                inventario.cantidad = nuevo_stock

            if nuevo_costo_compra is not None:
                inventario.costo_compra = nuevo_costo_compra
            if nuevo_costo_venta is not None:
                inventario.costo_venta = nuevo_costo_venta

            inventario.save()
            return Response(InventarioSerializer(inventario).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Error al actualizar inventario: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------- ELIMINAR INVENTARIO ----------
class EliminarInventario(APIView):
    def delete(self, request, inventario_id):
        tienda = getattr(request.user, "tienda", None)
        inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)
        inventario.delete()
        return Response({"message": "Inventario eliminado exitosamente"}, status=status.HTTP_200_OK)


# ---------- VERIFICAR STOCK ----------
class VerificarStock(APIView):
    def get(self, request, inventario_id):
        try:
            tienda = getattr(request.user, "tienda", None)
            inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)

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
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------- 10 PRODUCTOS CON MENOR STOCK ----------
class ProductosConMenorStockView(APIView):
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)

        inventarios = (
            Inventario.objects
            .filter(tienda=tienda)
            .select_related('producto')
            .order_by('cantidad')[:10]
        )
        

        data = [
            {
                "inventario":InventarioSerializer(inv).data,
                
                "item": ProductoSerializer(inv.producto).data,
            }
            for inv in inventarios
        ]

        return Response({"lowStockProducts": data}, status=status.HTTP_200_OK)


# ---------- BUSCAR INVENTARIO ----------

class BuscarInventarioAPIViewSinRangos(APIView):
    def post(self, request):
        data = request.data
        query = data.get("query", data)  # soporta {query:{}} o plano

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asociada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----- Parámetros -----
        nombre = (query.get("nombre") or "").strip().lower()
        nombre_normalizado = re.sub(r"\s+", " ", nombre).strip()

        categoria = query.get("categoria") or 0
        try:
            categoria = int(categoria)
        except (ValueError, TypeError):
            categoria = 0

        activo = query.get("activo", None)

        # ----- Filtros -----
        filtros = Q(tienda=tienda)

        if nombre_normalizado:
            palabras = nombre_normalizado.split(" ")
            for palabra in palabras:
                filtros &= (
                    Q(producto__nombre__icontains=palabra) |
                    Q(producto__descripcion__icontains=palabra)
                )

        if categoria > 0:
            filtros &= Q(producto__categoria_id=categoria)

        if activo is not None:
            filtros &= Q(activo=activo)

        # ----- Query -----
        inventarios = Inventario.objects.select_related("producto").filter(filtros).distinct()
        total_inventarios = inventarios.count()

        if total_inventarios == 0:
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
        paginator = InventarioPagination()
        result_page = paginator.paginate_queryset(inventarios, request)

        return Response({
            "count": total_inventarios,
            "next": paginator.page.next_page_number() if paginator.page.has_next() else None,
            "previous": paginator.page.previous_page_number() if paginator.page.has_previous() else None,
            "index_page": paginator.page.number - 1,  # página actual
            "length_pages": paginator.page.paginator.num_pages - 1,
            "results": InventarioSerializer(result_page, many=True).data,
            "search_products_found": "products_found"
        }, status=status.HTTP_200_OK)
        
# ---------- BUSCAR INVENTARIO ----------

class BuscarInventarioAPIView(APIView):
    def post(self, request):
        data = request.data
        query = data.get("query", data)  # soporta {query:{}} o plano

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asociada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----- Parámetros -----
        nombre = (query.get("nombre") or "").strip().lower()
        nombre_normalizado = re.sub(r"\s+", " ", nombre).strip()

        categoria = query.get("categoria") or 0
        try:
            categoria = int(categoria)
        except (ValueError, TypeError):
            categoria = 0

        activo = query.get("activo", None)

        # --- Filtros de stock ---
        stock_min = query.get("stock_min", None)
        stock_max = query.get("stock_max", None)

        # --- Filtros de precio compra ---
        precio_compra_min = query.get("precio_compra_min", None)
        precio_compra_max = query.get("precio_compra_max", None)

        # --- Filtros de precio venta ---
        precio_venta_min = query.get("precio_venta_min", None)
        precio_venta_max = query.get("precio_venta_max", None)

        # ----- Filtros -----
        filtros = Q(tienda=tienda)

        if nombre_normalizado:
            palabras = nombre_normalizado.split(" ")
            for palabra in palabras:
                filtros &= (
                    Q(producto__nombre__icontains=palabra) |
                    Q(producto__descripcion__icontains=palabra) |
                    Q(producto__sku__icontains=palabra) |
                    Q(producto__marca__icontains=palabra) |
                    Q(producto__modelo__icontains=palabra)
                    
                )

        if categoria > 0:
            filtros &= Q(producto__categoria_id=categoria)

        if activo is not None:
            filtros &= Q(activo=activo)

        # --- Stock ---
        if stock_min is not None:
            try:
                filtros &= Q(cantidad__gte=int(stock_min))
            except ValueError:
                pass
        if stock_max is not None:
            try:
                filtros &= Q(cantidad__lte=int(stock_max))
            except ValueError:
                pass

        # --- Precio de compra ---
        if precio_compra_min is not None:
            try:
                filtros &= Q(costo_compra__gte=float(precio_compra_min))
            except ValueError:
                pass
        if precio_compra_max is not None:
            try:
                filtros &= Q(costo_compra__lte=float(precio_compra_max))
            except ValueError:
                pass

        # --- Precio de venta ---
        if precio_venta_min is not None:
            try:
                filtros &= Q(costo_venta__gte=float(precio_venta_min))
            except ValueError:
                pass
        if precio_venta_max is not None:
            try:
                filtros &= Q(costo_venta__lte=float(precio_venta_max))
            except ValueError:
                pass

        # ----- Query -----
        inventarios = (
            Inventario.objects
            .select_related("producto")
            .filter(filtros)
            .distinct()
        )
        total_inventarios = inventarios.count()

        if total_inventarios == 0:
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
        paginator = InventarioPagination()
        result_page = paginator.paginate_queryset(inventarios, request)

        return Response({
            "count": total_inventarios,
            "next": paginator.page.next_page_number() if paginator.page.has_next() else None,
            "previous": paginator.page.previous_page_number() if paginator.page.has_previous() else None,
            "index_page": paginator.page.number - 1,  # página actual
            "length_pages": paginator.page.paginator.num_pages - 1,
            "results": InventarioSerializer(result_page, many=True).data,
            "search_products_found": "products_found"
        }, status=status.HTTP_200_OK)


