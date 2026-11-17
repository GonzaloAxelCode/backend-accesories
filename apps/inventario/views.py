
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from math import ceil
import re
from django.db.models import Q, Count, Sum

from django.contrib.auth import get_user_model
from apps.inventario.models import Inventario
from apps.inventario.serializers import InventarioSerializer
from apps.producto.models import Producto
from apps.producto.serializers import ProductoSerializer
from apps.proveedor.models import Proveedor
from core.permissions import CanCreateInventoryPermission, CanDeleteInventoryPermission, CanModifyInventoryPermission

User = get_user_model()


# ---------- PAGINACIÓN ----------
class InventarioPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------- CREAR INVENTARIO ----------
class CrearInventario(APIView):
    permission_classes=[IsAuthenticated,CanCreateInventoryPermission]
    def post(self, request):
        
        try:
            data = request.data
            tienda = getattr(request.user, "tienda", None)
            if not tienda:
                return Response({"error": "El usuario no tiene una tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)

            producto = get_object_or_404(Producto, id=data.get("producto"))
            #proveedor = get_object_or_404(Proveedor, id=data.get("proveedor"))
            user = request.user

            if Inventario.objects.filter(producto=producto, tienda=tienda).exists():
                return Response(
                    {"message": "Ya existe un inventario con este producto para esta tienda.",
                     "string_err": "inventario_existente"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Normalizar precios: evitar guardar None que luego rompe Decimal() en ventas
            def _to_decimal_or_zero(val):
                if val is None or val == "":
                    return 0.00
                try:
                    from decimal import Decimal
                    return Decimal(str(val))
                except Exception:
                    return 0.00

            nuevo_inventario = Inventario.objects.create(
                responsable=user,
                #proveedor=proveedor,
                descripcion=data.get("descripcion", ""),
                producto=producto,
                tienda=tienda,
                cantidad=data.get("cantidad", 0) or 0,
                stock_minimo=data.get("stock_minimo", 0) or 0,
                stock_maximo=data.get("stock_maximo", 100) or 100,
                costo_compra=_to_decimal_or_zero(data.get("costo_compra", 0.00)),
                costo_venta=_to_decimal_or_zero(data.get("costo_venta", 0.00)),
                costo=_to_decimal_or_zero(data.get("costo_compra", 0.00)),
                estado=data.get("estado", "Disponible"),
            )

            serializer = InventarioSerializer(nuevo_inventario)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetAllInventarioAPIView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = Inventario.objects.filter(tienda=tienda,activo=True)
        
        
        serializer = InventarioSerializer(qs, many=True)    

        return Response({
            
            "results": serializer.data
        })

class GetAllInventarioAPIViewWithpagination(APIView):
    permission_classes=[IsAuthenticated]
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
    permission_classes=[IsAuthenticated]
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
    permission_classes=[IsAuthenticated,CanModifyInventoryPermission]
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
    permission_classes=[IsAuthenticated,CanModifyInventoryPermission]
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

                inventario.cantidad = nuevo_stock

            if nuevo_costo_compra is not None:
                if nuevo_costo_compra == "":
                    inventario.costo_compra = 0.00
                else:
                    try:
                        from decimal import Decimal
                        inventario.costo_compra = Decimal(str(nuevo_costo_compra))
                    except Exception:
                        return Response({"error": "costo_compra inválido"}, status=status.HTTP_400_BAD_REQUEST)
            if nuevo_costo_venta is not None:
                if nuevo_costo_venta == "":
                    inventario.costo_venta = 0.00
                else:
                    try:
                        from decimal import Decimal
                        # permitir 0 pero no None; si viene None explícito lo convertimos a 0
                        if nuevo_costo_venta is None:
                            inventario.costo_venta = 0.00
                        else:
                            inventario.costo_venta = Decimal(str(nuevo_costo_venta))
                    except Exception:
                        return Response({"error": "costo_venta inválido"}, status=status.HTTP_400_BAD_REQUEST)

            inventario.save()
            return Response(InventarioSerializer(inventario).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Error al actualizar inventario: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------- ELIMINAR INVENTARIO ----------
class EliminarInventario(APIView):
    permission_classes=[IsAuthenticated,CanDeleteInventoryPermission]
    def delete(self, request, inventario_id):
        tienda = getattr(request.user, "tienda", None)
        inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)
        inventario.delete()
        return Response({"message": "Inventario eliminado exitosamente"}, status=status.HTTP_200_OK)


# ---------- VERIFICAR STOCK ----------
class VerificarStock(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, inventario_id):
        try:
            tienda = getattr(request.user, "tienda", None)
            inventario = get_object_or_404(Inventario, id=inventario_id, tienda=tienda)

            stock_status = "Stock en nivel adecuado"
            if inventario.cantidad == 0:
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
    permission_classes=[IsAuthenticated]
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)

        inventarios = (
            Inventario.objects
            .filter(tienda=tienda, activo=True, producto__activo=True)
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
    permission_classes=[IsAuthenticated]
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


# ---------- PORCENTAJE DE PRODUCTOS POR CATEGORÍA ----------
class PorcentajeProductosPorCategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_productos = Producto.objects.filter(tienda=tienda, activo=True).count()

        if total_productos == 0:
            return Response({"categorias": []}, status=status.HTTP_200_OK)

        productos_por_categoria = (
            Producto.objects
            .filter(tienda=tienda, activo=True)
            .values("categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        categorias = []
        for item in productos_por_categoria:
            nombre = item["categoria__nombre"] or "Sin categoría"
            cantidad = item["total"]
            porcentaje = round((cantidad / total_productos) * 100, 2)
            categorias.append({
                "categoria": nombre,
                "porcentaje": porcentaje
            })

        return Response({"categorias": categorias}, status=status.HTTP_200_OK)

# ---------- BUSCAR INVENTARIO ----------

class BuscarInventarioAPIView(APIView):
    permission_classes=[IsAuthenticated]
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


# ---------- RESUMEN TIENDA: TOTALES POR GRUPO + BAJO STOCK / CRÍTICO ----------
class ResumenTiendaView(APIView):
    permission_classes = [IsAuthenticated]

    # Grupos predefinidos del frontend (ver utils/categorias-predefinidas.ts)
    TELEFONOS_KEYWORDS = (
        "sellado", "nuevo", "seminuevo", "reacondicionado",
        "celular", "telefono", "teléfono", "telefonos", "teléfonos",
        "equipo", "equipos", "smartphone", "iphone", "celulares",
    )
    ACCESORIOS_KEYWORDS = (
        "funda", "mica", "hidrogel", "cargador", "cable",
        "audifono", "audífono", "parlante", "smartwatch", "correa",
        "reloj", "accesorio", "protector", "case", "vidrio",
        "templado", "cargadores", "cables", "fundas", "micas",
    )
    REPUESTOS_KEYWORDS = (
        "pantalla", "bateria", "batería", "pin de carga", "pin",
        "centro de carga", "flex", "camara", "cámara", "tapa",
        "repuesto", "repuestos", "tactil", "táctil", "display",
    )

    UMBRAL_BAJO_MIN = 1
    UMBRAL_BAJO_MAX = 3
    # 0 = agotado, 1-3 = bajo/crítico, 4+ = normal

    @classmethod
    def _clasificar(cls, categoria_nombre: str | None, categoria_tipo: str | None) -> str:
        nombre = (categoria_nombre or "").lower()
        tipo = (categoria_tipo or "").upper()
        if any(k in nombre for k in cls.TELEFONOS_KEYWORDS):
            return "telefonos"
        if any(k in nombre for k in cls.REPUESTOS_KEYWORDS) or tipo == "REPUESTO":
            return "repuestos"
        if any(k in nombre for k in cls.ACCESORIOS_KEYWORDS) or tipo == "ACCESORIO":
            return "accesorios"
        # Sin categoría o nombre no reconocido -> otros
        # Si es ACCESORIO genérico sin keyword igual va a accesorios (ya cubierto arriba).
        if not nombre or nombre in ("desconocido", "sin categoria", "sin categoría"):
            return "otros"
        return "otros"

    def get(self, request):
        from apps.repuesto.models import Repuesto
        from apps.celular.models import Celular
        from collections import Counter

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        inventarios = (
            Inventario.objects
            .filter(tienda=tienda, activo=True)
            .select_related("producto", "producto__categoria", "repuesto", "repuesto__categoria")
        )

        def _nuevo_grupo():
            return {"total": 0, "agotados": 0, "bajo_stock": 0, "critico": 0, "alerta_total": 0, "normal": 0,
                    "unidades": 0, "valorizacion": 0.0}

        grupos = {
            "accesorios": _nuevo_grupo(),
            "telefonos": _nuevo_grupo(),
            "repuestos": _nuevo_grupo(),
        }
        otros = 0
        otros_agotados = 0
        otros_bajo = 0
        agotados = 0
        critico = 0  # 1-3 unidades
        bajo_stock = 0  # 1-3 unidades (sin contar agotados); total alerta 0-3 = agotados + bajo

        def _contar_stock(grupo_dict: dict, cantidad: int):
            if cantidad == 0:
                grupo_dict["agotados"] += 1
            elif self.UMBRAL_BAJO_MIN <= cantidad <= self.UMBRAL_BAJO_MAX:
                grupo_dict["bajo_stock"] += 1
                grupo_dict["critico"] += 1
            else:
                grupo_dict["normal"] += 1

        def _sumar_unidades(grupo_dict: dict, cantidad: int, costo_unitario):
            """Suma unidades y valorización (costo × cantidad) del grupo."""
            try:
                costo = float(costo_unitario or 0)
            except (TypeError, ValueError):
                costo = 0.0
            grupo_dict["unidades"] += cantidad
            grupo_dict["valorizacion"] = round(grupo_dict.get("valorizacion", 0.0) + costo * cantidad, 2)

        telefonos_por_marca = Counter()
        repuestos_por_tipo = Counter()

        for inv in inventarios:
            # Los repuestos se cuentan SOLO desde el modelo Repuesto (ver abajo):
            # Repuesto.stock es el canónico que muestra el frontend. Contarlos
            # aquí también los duplicaría en grupos y en globales.
            if inv.repuesto_id:
                continue
            cantidad = inv.cantidad if inv.cantidad is not None else 0
            if cantidad == 0:
                agotados += 1
            elif self.UMBRAL_BAJO_MIN <= cantidad <= self.UMBRAL_BAJO_MAX:
                critico += 1
                bajo_stock += 1

            prod = inv.producto
            cat = getattr(prod, "categoria", None) if prod else None
            grupo = self._clasificar(
                getattr(cat, "nombre", None) if cat else None,
                getattr(cat, "tipo", None) if cat else None,
            )
            # Todo Inventario con producto ES un accesorio (Producto == accesorio
            # en este sistema): sin categoría caía en "otros" y las cards daban mal.
            if grupo == "otros" and inv.producto_id:
                grupo = "accesorios"
            if grupo in grupos:
                grupos[grupo]["total"] += 1
                _contar_stock(grupos[grupo], cantidad)
                _sumar_unidades(grupos[grupo], cantidad, getattr(inv, "costo_compra", 0))
                if grupo == "telefonos":
                    marca = (getattr(prod, "marca", None) or "").strip() if prod else ""
                    telefonos_por_marca[marca or "Sin marca"] += 1
                elif grupo == "repuestos":
                    repuestos_por_tipo[(getattr(cat, "nombre", None) or "Sin tipo").strip() or "Sin tipo"] += 1
            else:
                otros += 1
                if cantidad == 0:
                    otros_agotados += 1
                elif self.UMBRAL_BAJO_MIN <= cantidad <= self.UMBRAL_BAJO_MAX:
                    otros_bajo += 1

        repuestos_modelo = Repuesto.objects.filter(
            tienda=tienda, activo=True, is_deleted=False
        ).select_related("categoria")
        repuestos_modelo_total = repuestos_modelo.count()
        repuestos_agotados = repuestos_modelo.filter(stock=0).count()
        repuestos_bajo = repuestos_modelo.filter(
            stock__gte=self.UMBRAL_BAJO_MIN, stock__lte=self.UMBRAL_BAJO_MAX
        ).count()
        repuestos_normal = max(0, repuestos_modelo_total - repuestos_agotados - repuestos_bajo)
        rep_agg = repuestos_modelo.aggregate(u=Sum("stock"), v=Sum("valorizacion"))
        grupos["repuestos"]["unidades"] += int(rep_agg["u"] or 0)
        grupos["repuestos"]["valorizacion"] = round(float(rep_agg["v"] or 0), 2)

        for rep_cat_nombre in repuestos_modelo.values_list("categoria__nombre", flat=True):
            repuestos_por_tipo[(rep_cat_nombre or "Sin tipo").strip() or "Sin tipo"] += 1

        # Celulares (modelo Celular, uno por IMEI): ÚNICA fuente del grupo teléfonos.
        # Solo se cuentan los DISPONIBLES (disponible=True), sin importar el resto.
        # Además se informa cuántos NO están disponibles (detalle de la card).
        celulares_qs = Celular.objects.filter(tienda=tienda, activo=True, is_deleted=False)
        celulares_total = celulares_qs.filter(disponible=True).count()
        celulares_no_disp = celulares_qs.filter(disponible=False).count()
        grupos["telefonos"]["total"] += celulares_total
        grupos["telefonos"]["normal"] += celulares_total
        grupos["telefonos"]["unidades"] += celulares_total
        grupos["telefonos"]["no_disponibles"] = grupos["telefonos"].get("no_disponibles", 0) + celulares_no_disp
        cel_agg = celulares_qs.filter(disponible=True).aggregate(c=Sum("costo_compra"), v=Sum("precio_venta"))
        grupos["telefonos"]["valorizacion"] = round(float(cel_agg["c"] or 0), 2)
        grupos["telefonos"]["venta_potencial"] = round(float(cel_agg["v"] or 0), 2)
        # agotados/bajo_stock/critico quedan en 0: no disponibles no se cuentan.
        try:
            for marca_cel in celulares_qs.filter(disponible=True).values_list("marca", flat=True):
                telefonos_por_marca[(marca_cel or "Sin marca").strip() or "Sin marca"] += 1
        except Exception:
            pass

        # ÚNICA fuente de repuestos: el modelo Repuesto (ver skip de inv.repuesto_id arriba).
        grupos["repuestos"]["total"] += repuestos_modelo_total
        grupos["repuestos"]["agotados"] += repuestos_agotados
        grupos["repuestos"]["bajo_stock"] += repuestos_bajo
        grupos["repuestos"]["critico"] += repuestos_bajo
        grupos["repuestos"]["normal"] += repuestos_normal
        for g in grupos.values():
            g["alerta_total"] = g["agotados"] + g["bajo_stock"]

        accesorios = grupos["accesorios"]["total"]
        telefonos = grupos["telefonos"]["total"]
        total_repuestos = grupos["repuestos"]["total"]
        agotados_total = agotados + repuestos_agotados
        # Crítico y Bajo Stock comparten rango 1-3; se exponen ambos por compatibilidad
        critico_total = critico + repuestos_bajo
        bajo_stock_total = critico_total

        total_items = accesorios + telefonos + otros + total_repuestos

        return Response({
            "totales": {
                "accesorios": accesorios,
                "telefonos": telefonos,
                "repuestos": total_repuestos,
                "otros": otros,
                "total_items": total_items,
            },
            "stock": {
                "agotados": agotados_total,
                "bajo_stock": bajo_stock_total,
                "critico": critico_total,
                "alerta_total": agotados_total + bajo_stock_total,
                "umbral_bajo_min": self.UMBRAL_BAJO_MIN,
                "umbral_bajo_max": self.UMBRAL_BAJO_MAX,
            },
            "grupos": grupos,
            "telefonos_por_marca": [
                {"marca": marca, "total": total}
                for marca, total in sorted(telefonos_por_marca.items(), key=lambda x: -x[1])
            ],
            "repuestos_por_tipo": [
                {"tipo": tipo, "total": total}
                for tipo, total in sorted(repuestos_por_tipo.items(), key=lambda x: -x[1])
            ],
        }, status=status.HTTP_200_OK)


# ---------- DISTRIBUCIÓN DE STOCK POR NIVEL ----------
class DistribucionStockView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        inventarios = Inventario.objects.filter(tienda=tienda, activo=True)

        sin_stock = 0
        critico = 0
        bajo = 0
        normal = 0

        for inv in inventarios:
            if inv.cantidad == 0:
                sin_stock += 1
            elif inv.cantidad <= inv.stock_minimo * 0.5:
                critico += 1
            elif inv.cantidad <= inv.stock_minimo:
                bajo += 1
            else:
                normal += 1

        return Response({
            "distribucion": {
                "sin_stock": sin_stock,
                "critico": critico,
                "bajo": bajo,
                "normal": normal
            }
        }, status=status.HTTP_200_OK)


# ---------- PRODUCTOS POR RANGO DE PRECIOS ----------
class ProductosPorRangoPreciosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        inventarios = Inventario.objects.filter(tienda=tienda, activo=True)

        rangos_compra = []
        rangos_venta = []

        for i in range(0, 120, 10):
            minimo = i
            maximo = i + 10

            cantidad_compra = inventarios.filter(
                costo_compra__gte=minimo,
                costo_compra__lt=maximo
            ).count()

            cantidad_venta = inventarios.filter(
                costo_venta__gte=minimo,
                costo_venta__lt=maximo
            ).count()

            rangos_compra.append({
                "rango": f"{minimo} - {maximo}",
                "cantidad": cantidad_compra
            })

            rangos_venta.append({
                "rango": f"{minimo} - {maximo}",
                "cantidad": cantidad_venta
            })

        return Response({
            "por_precio_compra": rangos_compra,
            "por_precio_venta": rangos_venta
        }, status=status.HTTP_200_OK)


# ---------- TOP 10 ACCESORIOS POR COSTO (COMPRA / VENTA) ----------
class TopProductosCompraView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ?tipo=compra|venta  (acepta aliases: costo_compra, costo_venta, precio_venta)
        raw_tipo = str(request.query_params.get("tipo", "compra") or "compra").strip().lower()
        if raw_tipo in ("venta", "costo_venta", "precio_venta"):
            tipo = "venta"
            orden = "-costo_venta"
        else:
            tipo = "compra"
            orden = "-costo_compra"

        top_productos = (
            Inventario.objects
            .filter(tienda=tienda, activo=True, producto__isnull=False, producto__categoria__isnull=False)
            .select_related("producto", "producto__categoria")
            .order_by(orden, "-id")[:10]
        )

        productos = []
        for inv in top_productos:
            if not inv.producto or not inv.producto.categoria:
                continue
            categoria_nombre = inv.producto.categoria.nombre
            if not categoria_nombre:
                continue
            productos.append({
                "inventario_id": inv.id,
                "producto": inv.producto.nombre,
                "sku": inv.producto.sku,
                "categoria": categoria_nombre,
                "cantidad": inv.cantidad,
                "costo_compra": float(inv.costo_compra or 0),
                "costo_venta": float(inv.costo_venta or 0),
            })

        return Response({"top_productos_compra": productos, "tipo": tipo}, status=status.HTTP_200_OK)


# ---------- VALOR TOTAL EN SOLES POR CATEGORÍA (COMPRA / VENTA) ----------
class ValorPorCategoriaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        raw_tipo = str(request.query_params.get("tipo", "compra") or "compra").strip().lower()
        if raw_tipo in ("venta", "costo_venta", "precio_venta"):
            tipo = "venta"
            campo_costo = "costo_venta"
        else:
            tipo = "compra"
            campo_costo = "costo_compra"

        from django.db.models import DecimalField, ExpressionWrapper, F, Sum
        from django.db.models.functions import Coalesce

        valores = (
            Inventario.objects
            .filter(tienda=tienda, activo=True, producto__isnull=False, producto__categoria__isnull=False)
            .values("producto__categoria__nombre")
            .annotate(
                cantidad_productos=Count("id"),
                total_unidades=Sum("cantidad"),
                valor_total=Sum(
                    ExpressionWrapper(
                        Coalesce(F(campo_costo), 0) * F("cantidad"),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                ),
            )
            .order_by("-valor_total")[:10]
        )

        categorias = []
        for item in valores:
            nombre = item["producto__categoria__nombre"]
            if not nombre:
                continue
            categorias.append({
                "categoria": nombre,
                "cantidad_productos": item["cantidad_productos"],
                "total_unidades": item["total_unidades"] or 0,
                "valor_total": float(item["valor_total"] or 0),
            })

        return Response({"valor_por_categoria": categorias, "tipo": tipo}, status=status.HTTP_200_OK)


