from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Celular
from .serializers import CelularSerializer


from django.http import QueryDict


def _mutable_data(raw):
    # QueryDict.copy() hace deepcopy y falla con archivos (BufferedRandom).
    # .dict() conserva las referencias sin copiar.
    if isinstance(raw, QueryDict):
        return raw.dict()
    if hasattr(raw, "dict") and callable(getattr(raw, "dict")):
        try:
            return raw.dict()
        except Exception:
            pass
    return dict(raw)


def _tienda_or_400(request):
    tienda = getattr(request.user, "tienda", None)
    return tienda


class ListCelularesAPIView(APIView):
    """Traer + filtrar + buscar celulares de la tienda (paginado manual)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = _tienda_or_400(request)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=400)

        qs = Celular.objects.filter(tienda=tienda, is_deleted=False)

        # Filtros exactos
        for f in ("marca", "color", "memoria", "estado_equipo"):
            v = request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        v = request.query_params.get("activo")
        if v not in (None, ""):
            qs = qs.filter(activo=str(v).lower() in ("1", "true", "t", "si", "sí"))
        # bool filters
        for f in ("dualSim", "disponible"):
            v = request.query_params.get(f)
            if v not in (None, ""):
                qs = qs.filter(**{f: str(v).lower() in ("1", "true", "t", "si", "sí")})

        # Búsqueda libre: marca, modelo, imei1, imei2
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(marca__icontains=search) | Q(modelo__icontains=search)
                | Q(imei1__icontains=search) | Q(imei2__icontains=search)
            )

        qs = qs.order_by("-date_created")
        total = qs.count()

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 10)), 1), 100)
        except ValueError:
            return Response({"error": "page y page_size deben ser enteros."}, status=400)

        start = (page - 1) * page_size
        items = qs[start:start + page_size]
        data = CelularSerializer(items, many=True, context={"request": request}).data
        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "length_pages": (total + page_size - 1) // page_size if total else 0,
            "results": data,
        })


class CelularesPorMarcaView(APIView):
    """Top 10 marcas: total de equipos y cuántos están disponibles (tienda actual)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Count, Q

        tienda = _tienda_or_400(request)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=400)

        marcas = (
            Celular.objects
            .filter(tienda=tienda, activo=True, is_deleted=False)
            .values("marca")
            .annotate(
                total=Count("id"),
                disponibles=Count("id", filter=Q(disponible=True)),
            )
            .order_by("-total", "marca")[:10]
        )

        return Response({
            "por_marca": [
                {
                    "marca": (m["marca"] or "Sin marca").strip() or "Sin marca",
                    "total": m["total"] or 0,
                    "disponibles": m["disponibles"] or 0,
                }
                for m in marcas
            ]
        })


class TopCostoCompraCelularesView(APIView):
    """Top 10 modelos por costo (compra o venta): los más caros. ?tipo=compra|venta."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = _tienda_or_400(request)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=400)

        raw_tipo = str(request.query_params.get("tipo", "compra") or "compra").strip().lower()
        if raw_tipo in ("venta", "precio_venta", "costo_venta"):
            tipo = "venta"
            orden = "-precio_venta"
        else:
            tipo = "compra"
            orden = "-costo_compra"

        top = (
            Celular.objects
            .filter(tienda=tienda, activo=True, is_deleted=False)
            .order_by(orden, "-id")[:10]
        )

        items = []
        for c in top:
            img = None
            try:
                if c.imagen1 and hasattr(c.imagen1, "url"):
                    url = c.imagen1.url
                    img = request.build_absolute_uri(url) if url else None
            except Exception:
                img = None
            if not img:
                try:
                    if c.imagen2 and hasattr(c.imagen2, "url"):
                        url = c.imagen2.url
                        img = request.build_absolute_uri(url) if url else None
                except Exception:
                    img = None
            items.append(
                {
                    "id": c.id,
                    "marca": c.marca,
                    "modelo": c.modelo,
                    "imei": c.imei1,
                    "costo_compra": float(c.costo_compra or 0),
                    "precio_venta": float(c.precio_venta or 0),
                    "disponible": c.disponible,
                    "imagen": img,
                }
            )

        return Response({
            "tipo": tipo,
            "top_costo_compra": items,
        })


class GetCelularAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        tienda = _tienda_or_400(request)
        obj = get_object_or_404(Celular, id=id, tienda=tienda, is_deleted=False)
        return Response(CelularSerializer(obj, context={"request": request}).data)


IMAGEN_FIELDS = ("imagen1", "imagen2")


def _normalize_celular_data(raw):
    """Acepta aliases del form Angular (camelCase) + fotos[] y los mapea al modelo."""
    data = _mutable_data(raw)
    # Si fotos viene como múltiples archivos con la misma clave, recuperar la lista completa
    if isinstance(raw, QueryDict):
        fotos_list = raw.getlist("fotos")
        if len(fotos_list) > 1:
            data["fotos"] = fotos_list
    aliases = {
        "costoCompra": "costo_compra",
        "precioVenta": "precio_venta",
        "estado": "estado_equipo",
        "memoriaRam": "ram",
    }
    for src, dst in aliases.items():
        if src in data and dst not in data:
            data[dst] = data.pop(src)
    # fotos: string[] (máx 2) -> imagen1..imagen2 (solo los slots vacíos)
    fotos = data.pop("fotos", None)
    if fotos is not None:
        if not isinstance(fotos, list):
            fotos = [fotos]
        idx = 0
        for f in fotos[:2]:
            if f in (None, ""):
                continue
            while idx < 2 and data.get(IMAGEN_FIELDS[idx]):
                idx += 1
            if idx >= 2:
                break
            data[IMAGEN_FIELDS[idx]] = f
            idx += 1
    return data


def _imei_en_ventas(tienda_id, imeis):
    """True si alguno de esos IMEI ya aparece en ventas de la tienda."""
    from django.db.models import Q
    from apps.venta.models import VentaProducto

    imeis = [i for i in imeis if i]
    if not imeis:
        return False
    return VentaProducto.objects.filter(imei__in=imeis, venta__tienda_id=tienda_id).exists()


class CreateCelularAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tienda = _tienda_or_400(request)
        if not tienda:
            return Response({"error": "Usuario sin tienda asignada"}, status=400)
        serializer = CelularSerializer(data=_normalize_celular_data(request.data), context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        with transaction.atomic():
            obj = serializer.save(tienda=tienda, activo=True, is_deleted=False)
        return Response(
            {"message": "Celular creado exitosamente", "celular": CelularSerializer(obj, context={"request": request}).data},
            status=201,
        )


class UpdateCelularAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, id):
        tienda = _tienda_or_400(request)
        obj = get_object_or_404(Celular, id=id, tienda=tienda, is_deleted=False)
        serializer = CelularSerializer(obj, data=_normalize_celular_data(request.data), partial=True, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        # Un equipo vendido se puede modificar, pero sus IMEI quedan fijos salvo
        # que se reemplacen AMBOS por otros 2 no vendidos. Sin reemplazo no se
        # puede volver a poner disponible (sería revender la misma unidad).
        vendido_actual = _imei_en_ventas(tienda.id, [obj.imei1, obj.imei2])
        if vendido_actual:
            nuevos = serializer.validated_data
            nuevo_i1 = str(nuevos.get("imei1", obj.imei1) or "").strip()
            nuevo_i2 = str(nuevos.get("imei2", obj.imei2) or "").strip()
            cambio_imei = nuevo_i1 != (obj.imei1 or "").strip() or nuevo_i2 != (obj.imei2 or "").strip()
            if cambio_imei:
                if "imei1" not in nuevos or "imei2" not in nuevos:
                    return Response({"error": "Para cambiar el IMEI de un equipo vendido debes enviar los 2 IMEI nuevos"}, status=400)
                if _imei_en_ventas(tienda.id, [nuevo_i1, nuevo_i2]):
                    return Response({"error": "Uno de esos IMEI ya fue vendido y no se puede reutilizar"}, status=400)
            elif nuevos.get("disponible") is True:
                return Response({"error": "Este celular ya fue vendido y no se puede volver a poner disponible"}, status=400)
        # Si se reemplaza imagen, borrar anterior
        for field in IMAGEN_FIELDS:
            if field in serializer.validated_data and serializer.validated_data[field]:
                old = getattr(obj, field)
                if old:
                    old.delete(save=False)
        obj = serializer.save()
        return Response({"message": "Celular actualizado exitosamente", "celular": CelularSerializer(obj, context={"request": request}).data})


class DeleteCelularAPIView(APIView):
    """Borrado PERMANENTE: elimina el registro y sus imágenes."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        tienda = _tienda_or_400(request)
        obj = get_object_or_404(Celular, id=id, tienda=tienda, is_deleted=False)
        for field in IMAGEN_FIELDS:
            f = getattr(obj, field)
            if f:
                f.delete(save=False)
        obj.delete()
        return Response({"message": "Celular eliminado permanentemente"})


class ToggleActiveCelularAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        tienda = _tienda_or_400(request)
        obj = get_object_or_404(Celular, id=id, tienda=tienda, is_deleted=False)
        activo = request.data.get("activo")
        if activo is None:
            obj.activo = not obj.activo
        else:
            obj.activo = str(activo).lower() in ("1", "true", "t", "si", "sí") if isinstance(activo, str) else bool(activo)
        if not obj.activo:
            obj.disponible = False
        obj.save(update_fields=["activo", "disponible", "fecha_actualizacion"])
        return Response({"message": "Estado actualizado", "celular": CelularSerializer(obj, context={"request": request}).data})
