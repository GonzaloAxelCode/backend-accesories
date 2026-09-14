import json
from decimal import Decimal, InvalidOperation
from math import ceil, prod
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.inventario.models import Inventario
from apps.producto.models import Producto
from apps.producto.serializers import ProductoSerializer, ProductoDetalleCompletoSerializer
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
import base64












import json
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _decode_base64_image(data_uri: str):
    """
    Recibe algo como "data:image/jpeg;base64,AAAA..." (o solo el base64 puro)
    y devuelve un ContentFile listo para asignarse a un ImageField.
    Lanza ValueError si el contenido no es un base64 válido.
    """
    try:
        if isinstance(data_uri, list):
            data_uri = data_uri[0]

        if ";base64," in data_uri:
            header, b64data = data_uri.split(";base64,")
            # header típico: "data:image/jpeg"
            ext = header.split("/")[-1].split(";")[0] or "jpg"
        else:
            b64data = data_uri
            ext = "jpg"

        file_bytes = base64.b64decode(b64data)
        file_name = f"{uuid.uuid4().hex}.{ext}"
        return ContentFile(file_bytes, name=file_name)
    except Exception as exc:
        raise ValueError(f"Imagen base64 inválida: {exc}")


class CreateProductoAPIViewReactNative(APIView):
    permission_classes = [IsAuthenticated, CanCreateProductPermission]
    parser_classes = [JSONParser]  # ya no se acepta multipart, solo JSON

    def post(self, request):
        data = request.data.copy()

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "Usuario sin tienda asignada"}, status=400)

        # -------------------------------
        # Imagen: viene como base64 dentro del JSON, no como archivo multipart
        # -------------------------------
        imagen_raw = data.pop("imagen", None)
        imagen_file = None
        if imagen_raw:
            try:
                imagen_file = _decode_base64_image(imagen_raw)
            except ValueError as exc:
                return Response({"imagen": [str(exc)]}, status=400)

        # -------------------------------
        # Convertir caracteristicas JSON string → dict (o dejar dict tal cual)
        # -------------------------------
        caracteristicas_raw = data.get("caracteristicas")

        if caracteristicas_raw:
            if isinstance(caracteristicas_raw, (dict, list)):
                data["caracteristicas"] = caracteristicas_raw
            else:
                try:
                    data["caracteristicas"] = json.loads(caracteristicas_raw)
                except Exception:
                    return Response(
                        {"caracteristicas": ["El valor debe ser JSON válido."]},
                        status=400
                    )
        else:
            data["caracteristicas"] = {}

        # -------------------------------
        # Extraer campos de inventario (no pertenecen al Producto)
        # -------------------------------
        costo_compra_raw = data.get("costo_compra", None)
        costo_venta_raw = data.get("costo_venta", None)
        stock_raw = data.get("stock", data.get("cantidad", None))

        try:
            if costo_compra_raw is not None and costo_compra_raw != "":
                costo_compra = Decimal(str(costo_compra_raw))
                if costo_compra < 0:
                    return Response({"costo_compra": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                costo_compra = Decimal("0.00")
        except (InvalidOperation, ValueError, TypeError):
            return Response({"costo_compra": ["Debe ser un número decimal válido."]}, status=400)

        try:
            if costo_venta_raw is not None and costo_venta_raw != "":
                costo_venta = Decimal(str(costo_venta_raw))
                if costo_venta < 0:
                    return Response({"costo_venta": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                costo_venta = Decimal("0.00")
        except (InvalidOperation, ValueError, TypeError):
            return Response({"costo_venta": ["Debe ser un número decimal válido."]}, status=400)

        try:
            if stock_raw is not None and stock_raw != "":
                stock = int(Decimal(str(stock_raw)))  # soporta "10.0"
                if stock < 0:
                    return Response({"stock": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                stock = 1
        except (InvalidOperation, ValueError, TypeError):
            return Response({"stock": ["Debe ser un número entero válido."]}, status=400)

        # Remover campos de inventario antes de validar ProductoSerializer
        for key in ("costo_compra", "costo_venta", "stock", "cantidad"):
            data.pop(key, None)

        # -------------------------------
        # Crear producto + inventario de forma atómica
        # -------------------------------
        serializer = ProductoSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            print("ERROR al crear producto - errores de validación:", serializer.errors)
            return Response(serializer.errors, status=400)

        try:
            with transaction.atomic():
                producto = serializer.save(tienda=tienda, activo=True)

                # La imagen se guarda aparte, después de crear el producto
                if imagen_file:
                    producto.imagen.save(imagen_file.name, imagen_file, save=True)

                inventario = Inventario.objects.create(
                    responsable=request.user,
                    producto=producto,
                    tienda=tienda,
                    descripcion="Descripción",
                    cantidad=stock,
                    stock_minimo=1,
                    stock_maximo=15000,
                    costo_compra=costo_compra,
                    costo_venta=costo_venta,
                    costo=costo_compra,
                    estado="Disponible"
                )

                # Refrescar serializer para incluir imagen/producto actualizado
                producto_data = ProductoSerializer(producto, context={"request": request}).data

                from apps.inventario.serializers import InventarioSerializer
                inventario_data = InventarioSerializer(inventario).data

                return Response({
                    "message": "Producto e inventario creado exitosamente",
                    "producto": producto_data,
                    "inventario": inventario_data
                }, status=201)
        except Exception as e:
            print("ERROR al crear producto e inventario:", e)
            return Response(
                {"error": f"Error al crear producto e inventario: {str(e)}"},
                status=500
            )












































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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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
            # Si ya es dict (JSONParser) no parsear
            if isinstance(caracteristicas_raw, (dict, list)):
                data["caracteristicas"] = caracteristicas_raw
            else:
                try:
                    data["caracteristicas"] = json.loads(caracteristicas_raw)
                except Exception:
                    return Response(
                        {"caracteristicas": ["El valor debe ser JSON válido."]},
                        status=400
                    )
        else:
            data["caracteristicas"] = {}

        # -------------------------------
        # Extraer campos de inventario (no pertenecen al Producto)
        # -------------------------------
        # Soporta: costo_compra, costo_venta, stock/cantidad
        costo_compra_raw = data.get("costo_compra", None)
        costo_venta_raw = data.get("costo_venta", None)
        stock_raw = data.get("stock", data.get("cantidad", None))

        # Validar y convertir costo_compra
        try:
            if costo_compra_raw is not None and costo_compra_raw != "":
                costo_compra = Decimal(str(costo_compra_raw))
                if costo_compra < 0:
                    return Response({"costo_compra": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                costo_compra = Decimal("0.00")
        except (InvalidOperation, ValueError, TypeError):
            return Response({"costo_compra": ["Debe ser un número decimal válido."]}, status=400)

        try:
            if costo_venta_raw is not None and costo_venta_raw != "":
                costo_venta = Decimal(str(costo_venta_raw))
                if costo_venta < 0:
                    return Response({"costo_venta": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                costo_venta = Decimal("0.00")
        except (InvalidOperation, ValueError, TypeError):
            return Response({"costo_venta": ["Debe ser un número decimal válido."]}, status=400)

        try:
            if stock_raw is not None and stock_raw != "":
                stock = int(Decimal(str(stock_raw)))  # soporta "10.0"
                if stock < 0:
                    return Response({"stock": ["Debe ser mayor o igual a 0."]}, status=400)
            else:
                stock = 1
        except (InvalidOperation, ValueError, TypeError):
            return Response({"stock": ["Debe ser un número entero válido."]}, status=400)

        # Remover campos de inventario antes de validar ProductoSerializer
        for key in ("costo_compra", "costo_venta", "stock", "cantidad"):
            if key in data:
                try:
                    del data[key]
                except KeyError:
                    pass
                # QueryDict.copy() puede necesitar pop
                try:
                    data.pop(key, None)
                except Exception:
                    pass

        # Convertir QueryDict a dict normal si es necesario (para FormParser)
        try:
            data = data.dict()
        except AttributeError:
            data = dict(data)

        # -------------------------------
        # Crear producto + inventario de forma atómica
        # -------------------------------
        serializer = ProductoSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            print("ERROR al crear producto - errores de validación:", serializer.errors)
            return Response(serializer.errors, status=400)

        try:
            with transaction.atomic():
                producto = serializer.save(tienda=tienda, activo=True)

                inventario = Inventario.objects.create(
                    responsable=request.user,
                    producto=producto,
                    tienda=tienda,
                    descripcion="Descripción",
                    cantidad=stock,
                    stock_minimo=1,
                    stock_maximo=15000,
                    costo_compra=costo_compra,
                    costo_venta=costo_venta,
                    costo=costo_compra,
                    estado="Disponible"
                )

                # Refrescar serializer para incluir inventario creado
                producto_data = ProductoSerializer(producto, context={"request": request}).data

                # Incluir info de inventario en respuesta
                from apps.inventario.serializers import InventarioSerializer
                inventario_data = InventarioSerializer(inventario).data

                return Response({
                    "message": "Producto e inventario creado exitosamente",
                    "producto": producto_data,
                    "inventario": inventario_data
                }, status=201)
        except Exception as e:
            print("ERROR al crear producto e inventario:", e)
            return Response(
                {"error": f"Error al crear producto e inventario: {str(e)}"},
                status=500
            )



class UpdateProductoAPIView(APIView):
    permission_classes = [IsAuthenticated, CanUpdateProductPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)

        data = request.data.copy()

        # ------------------------------------
        # Convertir JSON string → dict
        # ------------------------------------
        caracteristicas_raw = data.get("caracteristicas")

        if caracteristicas_raw is not None:
            if isinstance(caracteristicas_raw, (dict, list)):
                data["caracteristicas"] = caracteristicas_raw
            elif caracteristicas_raw == "":
                data["caracteristicas"] = {}
            else:
                try:
                    data["caracteristicas"] = json.loads(caracteristicas_raw)
                except Exception:
                    return Response(
                        {"caracteristicas": ["El valor debe ser JSON válido."]},
                        status=400
                    )

        # -------------------------------
        # Extraer campos de inventario (opcionales en update)
        # -------------------------------
        costo_compra_raw = data.get("costo_compra", None)
        costo_venta_raw = data.get("costo_venta", None)
        stock_raw = data.get("stock", data.get("cantidad", None))

        # Detectar si el cliente envió cada campo (para update parcial)
        has_costo_compra = "costo_compra" in data
        has_costo_venta = "costo_venta" in data
        has_stock = "stock" in data or "cantidad" in data

        costo_compra = None
        costo_venta = None
        stock = None

        if has_costo_compra:
            if costo_compra_raw == "" or costo_compra_raw is None:
                return Response({"costo_compra": ["No puede ser vacío."]}, status=400)
            try:
                costo_compra = Decimal(str(costo_compra_raw))
                if costo_compra < 0:
                    return Response({"costo_compra": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"costo_compra": ["Debe ser un número decimal válido."]}, status=400)

        if has_costo_venta:
            if costo_venta_raw == "" or costo_venta_raw is None:
                return Response({"costo_venta": ["No puede ser vacío."]}, status=400)
            try:
                costo_venta = Decimal(str(costo_venta_raw))
                if costo_venta < 0:
                    return Response({"costo_venta": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"costo_venta": ["Debe ser un número decimal válido."]}, status=400)

        if has_stock:
            if stock_raw == "" or stock_raw is None:
                return Response({"stock": ["No puede ser vacío."]}, status=400)
            try:
                stock = int(Decimal(str(stock_raw)))
                if stock < 0:
                    return Response({"stock": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"stock": ["Debe ser un número entero válido."]}, status=400)

        # Remover campos de inventario antes de validar ProductoSerializer
        for key in ("costo_compra", "costo_venta", "stock", "cantidad"):
            if key in data:
                try:
                    del data[key]
                except KeyError:
                    pass
                try:
                    data.pop(key, None)
                except Exception:
                    pass

        # Convertir QueryDict a dict normal
        try:
            data = data.dict()
        except AttributeError:
            data = dict(data)

        # ------------------------------------
        # Serializar actualización + inventario de forma atómica
        # ------------------------------------
        serializer = ProductoSerializer(producto, data=data, partial=True, context={"request": request})

        if not serializer.is_valid():
            print("ERROR al actualizar producto e inventario - errores de validación:", serializer.errors)
            return Response(serializer.errors, status=400)

        try:
            with transaction.atomic():
                producto_actualizado = serializer.save()

                # Actualizar/crear inventario si se envió al menos un campo de inventario
                inventario = None
                if has_costo_compra or has_costo_venta or has_stock:
                    # Buscar inventario existente para esta tienda+producto
                    inventario = Inventario.objects.select_for_update().filter(
                        producto=producto_actualizado, tienda=tienda
                    ).first()

                    if inventario:
                        if has_costo_compra:
                            inventario.costo_compra = costo_compra
                            inventario.costo = costo_compra
                        if has_costo_venta:
                            inventario.costo_venta = costo_venta
                        if has_stock:
                            inventario.cantidad = stock
                        inventario.save()
                    else:
                        # Si no existe, crearlo (usa valores enviados o defaults)
                        inventario = Inventario.objects.create(
                            responsable=request.user,
                            producto=producto_actualizado,
                            tienda=tienda,
                            descripcion="Descripción",
                            cantidad=stock if has_stock else 1,
                            stock_minimo=1,
                            stock_maximo=15000,
                            costo_compra=costo_compra if has_costo_compra else Decimal("0.00"),
                            costo_venta=costo_venta if has_costo_venta else Decimal("0.00"),
                            costo=costo_compra if has_costo_compra else Decimal("0.00"),
                            estado="Disponible"
                        )
                else:
                    # No se pidieron cambios de inventario, solo obtener el actual si existe
                    inventario = Inventario.objects.filter(producto=producto_actualizado, tienda=tienda).first()

                producto_data = ProductoSerializer(producto_actualizado, context={"request": request}).data

                response_data = {
                    "message": "Producto actualizado exitosamente",
                    "producto": producto_data,
                }
                if inventario:
                    from apps.inventario.serializers import InventarioSerializer
                    response_data["inventario"] = InventarioSerializer(inventario).data

                return Response(response_data, status=200)
        except Exception as e:
            print("ERROR al actualizar producto e inventario:", e)
            return Response(
                {"error": f"Error al actualizar producto e inventario: {str(e)}"},
                status=500
            )



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


# ---------- BUSCAR PRODUCTO POR SKU CON DETALLE COMPLETO ----------
class BuscarProductoPorSKUAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        sku = request.query_params.get('sku', '').strip()
        
        if not sku:
            return Response(
                {"error": "El parámetro SKU es requerido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            producto = Producto.objects.get(sku__iexact=sku, tienda=tienda, activo=True)
            serializer = ProductoDetalleCompletoSerializer(producto)
            
            return Response({
                "message": "Producto encontrado",
                "producto": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Producto.DoesNotExist:
            return Response(
                {"error": f"No se encontró un producto con SKU: {sku}"},
                status=status.HTTP_404_NOT_FOUND
            )



























import base64
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response




def _decode_base64_image(data_uri: str):
    """
    Recibe algo como "data:image/jpeg;base64,AAAA..." (o solo el base64 puro)
    y devuelve un ContentFile listo para asignarse a un ImageField.
    Lanza ValueError si el contenido no es un base64 válido.
    """
    try:
        if isinstance(data_uri, list):
            data_uri = data_uri[0]

        if ";base64," in data_uri:
            header, b64data = data_uri.split(";base64,")
            ext = header.split("/")[-1].split(";")[0] or "jpg"
        else:
            b64data = data_uri
            ext = "jpg"

        file_bytes = base64.b64decode(b64data)
        file_name = f"{uuid.uuid4().hex}.{ext}"
        return ContentFile(file_bytes, name=file_name)
    except Exception as exc:
        raise ValueError(f"Imagen base64 inválida: {exc}")


import base64
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response






def _decode_base64_image(data_uri: str):
    """
    Recibe algo como "data:image/jpeg;base64,AAAA..." (o solo el base64 puro)
    y devuelve un ContentFile listo para asignarse a un ImageField.
    Lanza ValueError si el contenido no es un base64 válido.
    """
    try:
        if isinstance(data_uri, list):
            data_uri = data_uri[0]

        if ";base64," in data_uri:
            header, b64data = data_uri.split(";base64,")
            ext = header.split("/")[-1].split(";")[0] or "jpg"
        else:
            b64data = data_uri
            ext = "jpg"

        file_bytes = base64.b64decode(b64data)
        file_name = f"{uuid.uuid4().hex}.{ext}"
        return ContentFile(file_bytes, name=file_name)
    except Exception as exc:
        raise ValueError(f"Imagen base64 inválida: {exc}")


class InventarioNoEncontradoError(Exception):
    """Se lanza cuando se pide actualizar inventario pero no existe registro."""
    pass


class UpdateProductoAPIViewReactNative(APIView):
    permission_classes = [IsAuthenticated, CanUpdateProductPermission]
    parser_classes = [JSONParser]  # solo JSON, sin multipart

    def put(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        producto = get_object_or_404(Producto, id=id, tienda=tienda)

        data = request.data.copy()

        # ------------------------------------
        # Imagen: viene como base64 dentro del JSON (opcional en update)
        # ------------------------------------
        imagen_raw = data.pop("imagen", None)
        imagen_file = None
        has_imagen = imagen_raw is not None and imagen_raw != ""
        if has_imagen:
            try:
                imagen_file = _decode_base64_image(imagen_raw)
            except ValueError as exc:
                return Response({"imagen": [str(exc)]}, status=400)

        # ------------------------------------
        # Convertir JSON string → dict
        # ------------------------------------
        caracteristicas_raw = data.get("caracteristicas")

        if caracteristicas_raw is not None:
            if isinstance(caracteristicas_raw, (dict, list)):
                data["caracteristicas"] = caracteristicas_raw
            elif caracteristicas_raw == "":
                data["caracteristicas"] = {}
            else:
                try:
                    data["caracteristicas"] = json.loads(caracteristicas_raw)
                except Exception:
                    return Response(
                        {"caracteristicas": ["El valor debe ser JSON válido."]},
                        status=400
                    )

        # -------------------------------
        # Extraer campos de inventario (opcionales en update)
        # -------------------------------
        costo_compra_raw = data.get("costo_compra", None)
        costo_venta_raw = data.get("costo_venta", None)
        stock_raw = data.get("stock", data.get("cantidad", None))

        has_costo_compra = "costo_compra" in data
        has_costo_venta = "costo_venta" in data
        has_stock = "stock" in data or "cantidad" in data

        costo_compra = None
        costo_venta = None
        stock = None

        if has_costo_compra:
            if costo_compra_raw == "" or costo_compra_raw is None:
                return Response({"costo_compra": ["No puede ser vacío."]}, status=400)
            try:
                costo_compra = Decimal(str(costo_compra_raw))
                if costo_compra < 0:
                    return Response({"costo_compra": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"costo_compra": ["Debe ser un número decimal válido."]}, status=400)

        if has_costo_venta:
            if costo_venta_raw == "" or costo_venta_raw is None:
                return Response({"costo_venta": ["No puede ser vacío."]}, status=400)
            try:
                costo_venta = Decimal(str(costo_venta_raw))
                if costo_venta < 0:
                    return Response({"costo_venta": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"costo_venta": ["Debe ser un número decimal válido."]}, status=400)

        if has_stock:
            if stock_raw == "" or stock_raw is None:
                return Response({"stock": ["No puede ser vacío."]}, status=400)
            try:
                stock = int(Decimal(str(stock_raw)))
                if stock < 0:
                    return Response({"stock": ["Debe ser mayor o igual a 0."]}, status=400)
            except (InvalidOperation, ValueError, TypeError):
                return Response({"stock": ["Debe ser un número entero válido."]}, status=400)

        # Remover campos de inventario antes de validar ProductoSerializer
        for key in ("costo_compra", "costo_venta", "stock", "cantidad"):
            data.pop(key, None)

        # ------------------------------------
        # Serializar actualización + inventario de forma atómica
        # ------------------------------------
        serializer = ProductoSerializer(producto, data=data, partial=True, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            with transaction.atomic():
                producto_actualizado = serializer.save()

                # Guardar imagen nueva si se envió
                if has_imagen and imagen_file:
                    producto_actualizado.imagen.save(imagen_file.name, imagen_file, save=True)

                inventario = None
                if has_costo_compra or has_costo_venta or has_stock:
                    inventario = Inventario.objects.select_for_update().filter(
                        producto=producto_actualizado, tienda=tienda
                    ).first()

                    if inventario is None:
                        # ANTES: se creaba uno nuevo con defaults, enmascarando el
                        # problema real (producto sin inventario, mismatch de tienda, etc).
                        # AHORA: se falla explícitamente. Esto hace raise dentro del
                        # `with transaction.atomic()`, por lo que Django revierte
                        # TODO (incluyendo los cambios ya hechos al producto e imagen).
                        raise InventarioNoEncontradoError(
                            "No existe un inventario para este producto en tu tienda. "
                            "No se puede actualizar stock/costos de un inventario inexistente."
                        )

                    if has_costo_compra:
                        inventario.costo_compra = costo_compra
                        inventario.costo = costo_compra
                    if has_costo_venta:
                        inventario.costo_venta = costo_venta
                    if has_stock:
                        inventario.cantidad = stock
                    inventario.save()
                else:
                    inventario = Inventario.objects.filter(producto=producto_actualizado, tienda=tienda).first()

                producto_data = ProductoSerializer(producto_actualizado, context={"request": request}).data

                response_data = {
                    "message": "Producto actualizado exitosamente",
                    "producto": producto_data,
                }
                if inventario:
                    from apps.inventario.serializers import InventarioSerializer
                    response_data["inventario"] = InventarioSerializer(inventario).data

                return Response(response_data, status=200)

        except InventarioNoEncontradoError as e:
            # 404/409 en vez de 500: es un error de estado de datos, no del servidor.
            return Response({"error": str(e)}, status=409)
        except Exception as e:
            print("ERROR al actualizar producto e inventario:", e)
            return Response(
                {"error": f"Error al actualizar producto e inventario: {str(e)}"},
                status=500
            )