from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

import json
from pathlib import Path
from django.conf import settings

from apps.categoria.serializers import CategoriaSerializer
from apps.tienda.models import Tienda
from .models import Categoria


SEED_JSON_PATH = Path(settings.BASE_DIR) / "apps" / "categoria" / "data" / "categorias_accesorios_peru.json"


def _load_seed_json():
    if not SEED_JSON_PATH.exists():
        return None, f"No se encontró el archivo seed: {SEED_JSON_PATH}"
    try:
        with open(SEED_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return None, f"Error leyendo seed JSON: {e}"
    if not isinstance(data, list):
        return None, "El seed JSON debe ser una lista."
    return data, None


# Crear una nueva categoria
class CreateCategoria(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()

        # Si no viene `caracteristicas_template`, lo forzamos a lista vacía
        if "caracteristicas_template" not in data:
            data["caracteristicas_template"] = []

        # Las creadas manualmente siempre son editables
        data["update_enable"] = True

        # Tienda destino: por defecto la del usuario. Un superusuario puede
        # crear en otra tienda (ej. admin gestionando store/2) pasándola en `tienda`.
        tienda = request.user.tienda
        try:
            tienda_id = data.pop("tienda", None)
        except Exception:
            tienda_id = data.get("tienda", None)
        if isinstance(tienda_id, (list, tuple)):
            tienda_id = tienda_id[-1] if tienda_id else None
        if tienda_id not in (None, ""):
            try:
                tienda_obj = Tienda.objects.get(id=int(tienda_id))
            except (ValueError, TypeError, Tienda.DoesNotExist):
                return Response({"tienda": ["Tienda no válida."]}, status=status.HTTP_400_BAD_REQUEST)
            if not request.user.is_superuser and (not tienda or tienda_obj.id != tienda.id):
                return Response({"detail": "No autorizado para crear en otra tienda."}, status=status.HTTP_403_FORBIDDEN)
            tienda = tienda_obj

        if tienda is None:
            return Response({"detail": "El usuario no tiene tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CategoriaSerializer(data=data)
        if serializer.is_valid():
            serializer.save(tienda=tienda)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Obtener todas las categorias
class GetAllCategorias(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        tienda = request.user.tienda
        # ?tienda= para ver las de otra tienda (solo superusuario, ej. admin viendo store/2)
        tienda_param = (request.query_params.get("tienda") or "").strip()
        if tienda_param:
            try:
                from apps.tienda.models import Tienda
                tienda = Tienda.objects.get(id=int(tienda_param))
            except (ValueError, Tienda.DoesNotExist):
                return Response({"detail": "Tienda no válida."}, status=status.HTTP_400_BAD_REQUEST)
            # Solo superusuario puede ver otras tiendas; la propia siempre se permite
            if not request.user.is_superuser and (not request.user.tienda or tienda.id != request.user.tienda.id):
                return Response({"detail": "No autorizado para ver otras tiendas."}, status=status.HTTP_403_FORBIDDEN)
        categorias = Categoria.objects.filter(tienda=tienda,activo=True)
        # Filtro ?tipo=REPUESTO|ACCESORIO|TODO. Por defecto solo ACCESORIOS.
        tipo = (request.query_params.get("tipo") or "ACCESORIO").strip().upper()
        if tipo not in ("REPUESTO", "ACCESORIO", "TODO"):
            return Response({"detail": "tipo debe ser REPUESTO, ACCESORIO o TODO."}, status=status.HTTP_400_BAD_REQUEST)
        if tipo != "TODO":
            categorias = categorias.filter(tipo=tipo)
        serializer = CategoriaSerializer(categorias, many=True,)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Obtener una categoria por ID
class GetCategoria(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        serializer = CategoriaSerializer(categoria)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Actualizar una categoria por ID
class UpdateCategoria(APIView):
    permission_classes = [IsAuthenticated]    
    def put(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        # Bloqueo de edición para categorías predefinidas del seed
        if categoria.update_enable is False:
            return Response(
                {"detail": "Esta categoría es predefinida del sistema y no se puede editar (update_enable=False)."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        # Las personales siempre quedan en True, no se permite pasarlas a False por aquí
        if "update_enable" in data:
            data.pop("update_enable")
        serializer = CategoriaSerializer(categoria, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Desactivar una categoria por ID
class DeactivateCategoria(APIView):
    
    permission_classes = [IsAuthenticated]    
    def patch(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        categoria.activo = False
        categoria.nombre = f"{categoria.nombre}(Delete)_{categoria.id}" # type: ignore
        categoria.save()
        return Response({"message": "Categoria desactivada exitosamente"}, status=status.HTTP_200_OK)
class DeleteCategoria(APIView):
    permission_classes = [IsAuthenticated]    
    def delete(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        categoria.activo = False
        categoria.nombre = f"{categoria.nombre}(Delete)_{categoria.id}" # type: ignore
        categoria.save()
        return Response({"message": "Categoria eliminada exitosamente"}, status=status.HTTP_200_OK)


def _resolve_seed_tienda(request, explicit_id=None):
    """Resuelve la tienda destino para seed/vaciar, igual que CreateCategoria.

    - Usuario normal: solo su propia tienda.
    - Superusuario: puede pasar `tienda` (body o query) para gestionar otra tienda;
      si no la pasa, usa la propia. Si no hay tienda resolvible, devuelve (None, Response).
    """
    raw = explicit_id
    if raw in (None, ""):
        raw = request.query_params.get("tienda", None)
    if raw in (None, "") and isinstance(request.data, dict):
        raw = request.data.get("tienda", None)
    if hasattr(request.data, "get") and raw in (None, ""):
        try:
            raw = request.data.get("tienda", None)
        except Exception:
            pass
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None

    tienda = request.user.tienda
    if raw not in (None, ""):
        try:
            tienda_obj = Tienda.objects.get(id=int(raw))
        except (ValueError, TypeError, Tienda.DoesNotExist):
            return None, Response({"detail": "Tienda no válida."}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.is_superuser and (not tienda or tienda_obj.id != tienda.id):
            return None, Response({"detail": "No autorizado para gestionar otra tienda."}, status=status.HTTP_403_FORBIDDEN)
        return tienda_obj, None

    if tienda is None:
        if request.user.is_superuser:
            return None, Response(
                {"detail": "Indica la tienda destino (tienda=<id>). El superusuario sin tienda asignada debe especificarla."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None, Response({"detail": "El usuario no tiene tienda asignada."}, status=status.HTTP_400_BAD_REQUEST)
    return tienda, None


# Carga masiva del JSON local (60 categorías accesorios Perú).
# Idempotente POR TIENDA: si el nombre ya existe en esa tienda (case-insensitive) se obvia.
class SeedCategoriasAccesorios(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Solo un superusuario puede cargar las categorías predefinidas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data, err = _load_seed_json()
        if err:
            return Response({"detail": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        tienda, err_resp = _resolve_seed_tienda(request)
        if err_resp is not None:
            return err_resp

        creadas = 0
        omitidas = 0
        detalle_omitidas = []

        for item in data or []:
            nombre = str(item.get("nombre", "")).strip()
            if not nombre:
                omitidas += 1
                continue
            # Obviar solo si ya existe EN ESTA TIENDA (antes era global por unique=True).
            if Categoria.objects.filter(tienda=tienda, nombre__iexact=nombre).exists():
                omitidas += 1
                detalle_omitidas.append(nombre)
                continue
            try:
                Categoria.objects.create(
                    nombre=nombre,
                    descripcion=item.get("descripcion", ""),
                    caracteristicas_template=item.get("caracteristicas_template", []),
                    orden=item.get("orden", 0) or 0,
                    tipo=item.get("tipo", "ACCESORIO") or "ACCESORIO",
                    activo=True,
                    destacado=False,
                    update_enable=False,  # predefinidas: no editables
                    tienda=tienda,
                )
            except IntegrityError:
                # Carrera o unique legacy (categoria_categoria_nombre_key) sin migrar:
                # no tumbar todo el seed, contar como omitida.
                omitidas += 1
                detalle_omitidas.append(nombre)
                continue
            creadas += 1

        return Response(
            {
                "message": f"Seed completado: {creadas} creadas, {omitidas} omitidas.",
                "creadas": creadas,
                "omitidas": omitidas,
                "omitidas_nombres": detalle_omitidas,
                "total_json": len(data or []),
            },
            status=status.HTTP_201_CREATED,
        )


# Eliminación PERMANENTE de las categorías predefinidas DEL JSON, solo en la tienda destino.
# No toca las creadas por el usuario (update_enable=True).
class DeleteSeedCategoriasAccesorios(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Solo un superusuario puede vaciar las categorías predefinidas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data, err = _load_seed_json()
        if err:
            return Response({"detail": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        tienda, err_resp = _resolve_seed_tienda(request)
        if err_resp is not None:
            return err_resp

        nombres = [str(x.get("nombre", "")).strip() for x in (data or []) if str(x.get("nombre", "")).strip()]
        if not nombres:
            return Response({"detail": "Seed vacío, nada que eliminar."}, status=status.HTTP_400_BAD_REQUEST)

        qs = Categoria.objects.filter(tienda=tienda, update_enable=False, nombre__in=nombres)
        eliminadas_nombres = list(qs.values_list("nombre", flat=True))
        total, _ = qs.delete()  # hard delete permanente

        return Response(
            {
                "message": f"Eliminación permanente completada: {len(eliminadas_nombres)} eliminadas.",
                "eliminadas": len(eliminadas_nombres),
                "eliminadas_nombres": eliminadas_nombres,
                "total_json": len(nombres),
            },
            status=status.HTTP_200_OK,
        )
