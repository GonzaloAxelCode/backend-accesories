from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.http import QueryDict
from .models import Repuesto
from .serializers import RepuestoSerializer


def _mutable_data(raw):
    if isinstance(raw, QueryDict):
        return raw.dict()
    if hasattr(raw, "dict") and callable(getattr(raw, "dict")):
        try:
            return raw.dict()
        except Exception:
            pass
    return dict(raw)


class ListRepuestosAPIView(APIView):
    """Traer + filtrar + buscar repuestos de la tienda (paginado manual)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "El usuario no tiene una tienda asignada."}, status=400)

        qs = Repuesto.objects.filter(tienda=tienda, is_deleted=False).select_related("proveedor", "categoria")

        for f in ("ubicacion", "proveedor", "categoria"):
            v = request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        v = request.query_params.get("activo")
        if v not in (None, ""):
            qs = qs.filter(activo=str(v).lower() in ("1", "true", "t", "si", "sí"))

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(nombre__icontains=search) | Q(modelos_compatibles__icontains=search))

        qs = qs.order_by("-date_created")
        total = qs.count()

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 10)), 1), 100)
        except ValueError:
            return Response({"error": "page y page_size deben ser enteros."}, status=400)

        start = (page - 1) * page_size
        items = list(qs[start:start + page_size])
        data = RepuestoSerializer(items, many=True, context={"request": request}).data
        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "length_pages": (total + page_size - 1) // page_size if total else 0,
            "results": data,
        })


class GetRepuestoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        obj = get_object_or_404(Repuesto, id=id, tienda=tienda, is_deleted=False)
        return Response(RepuestoSerializer(obj, context={"request": request}).data)


REPUESTO_IMAGEN_FIELDS = ("imagen1", "imagen2")


def _normalize_repuesto_data(raw):
    data = _mutable_data(raw)
    if isinstance(raw, QueryDict):
        fotos_list = raw.getlist("fotos")
        if len(fotos_list) > 1:
            data["fotos"] = fotos_list
    # aliases camelCase / nombre corto del form
    if "modelos" in data and "modelos_compatibles" not in data:
        data["modelos_compatibles"] = data.pop("modelos")
    # frontend manda "cantidad", el modelo usa "stock"
    if "cantidad" in data and "stock" not in data:
        data["stock"] = data.pop("cantidad")
    elif "cantidad" in data:
        data.pop("cantidad")
    # FK opcionales: "" -> None (sin proveedor / sin categoria)
    for fk in ("proveedor", "categoria"):
        if data.get(fk) in ("", "null", "undefined", "0"):
            data[fk] = None
    # stock/valorizacion obligatorios en create: si faltan se dejan ausentes (400);
    # si vienen "" se dejan para que DRF los rechace (400). No convertir a 0.
    if data.get("stock") is None:
        data.pop("stock", None)
    if data.get("valorizacion") is None:
        data.pop("valorizacion", None)
    u = data.get("ubicacion")
    if isinstance(u, str):
        data["ubicacion"] = u.strip() or None
    # fotos: list (máx 2) -> imagen1..imagen2
    fotos = data.pop("fotos", None)
    if fotos is not None:
        if not isinstance(fotos, list):
            fotos = [fotos]
        idx = 0
        for f in fotos[:2]:
            if f in (None, ""):
                continue
            while idx < 2 and data.get(REPUESTO_IMAGEN_FIELDS[idx]):
                idx += 1
            if idx >= 2:
                break
            data[REPUESTO_IMAGEN_FIELDS[idx]] = f
            idx += 1
    return data


class CreateRepuestoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"error": "Usuario sin tienda asignada"}, status=400)

        data = _normalize_repuesto_data(request.data)
        serializer = RepuestoSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        obj = serializer.save(tienda=tienda, activo=True, is_deleted=False)
        return Response(
            {"message": "Repuesto creado exitosamente", "repuesto": RepuestoSerializer(obj, context={"request": request}).data},
            status=201,
        )


class UpdateRepuestoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        obj = get_object_or_404(Repuesto, id=id, tienda=tienda, is_deleted=False)

        data = _normalize_repuesto_data(request.data)
        serializer = RepuestoSerializer(obj, data=data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        for field in REPUESTO_IMAGEN_FIELDS:
            if field in serializer.validated_data and serializer.validated_data[field]:
                old = getattr(obj, field)
                if old:
                    old.delete(save=False)
        obj = serializer.save()
        return Response({"message": "Repuesto actualizado exitosamente", "repuesto": RepuestoSerializer(obj, context={"request": request}).data})


class DeleteRepuestoAPIView(APIView):
    """Soft delete: is_deleted=True, activo=False."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        obj = get_object_or_404(Repuesto, id=id, tienda=tienda, is_deleted=False)
        obj.is_deleted = True
        obj.activo = False
        obj.nombre = f"{obj.nombre}(Delete)_{obj.id}"
        obj.save(update_fields=["is_deleted", "activo", "nombre", "fecha_actualizacion"])
        return Response({"message": "Repuesto eliminado exitosamente"})


class ToggleActiveRepuestoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        tienda = getattr(request.user, "tienda", None)
        obj = get_object_or_404(Repuesto, id=id, tienda=tienda, is_deleted=False)
        activo = request.data.get("activo")
        if activo is None:
            obj.activo = not obj.activo
        else:
            obj.activo = str(activo).lower() in ("1", "true", "t", "si", "sí") if isinstance(activo, str) else bool(activo)
        obj.save(update_fields=["activo", "fecha_actualizacion"])
        return Response({"message": "Estado actualizado", "repuesto": RepuestoSerializer(obj, context={"request": request}).data})
