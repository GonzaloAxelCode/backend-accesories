from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser

from core.permissions import IsSuperUser, IsAdminTienda
from .models import Tienda
from .serializers import TiendaSerializer
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated

User = get_user_model()


# ============================================
# SUPERUSER: Gestionar tiendas
# ============================================

class GetAllTiendas(APIView):
    """Superuser + AdminTienda: ver tiendas (superuser ve todas, admin ve la suya + sucursales)"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            tiendas = Tienda.objects.filter(is_deleted=False)
        else:
            # Solo admin_tienda puede listar: verificar que sea propietario
            is_admin = user.tienda and user.tienda.propietario_id == user.id  # type: ignore
            if not is_admin:
                return Response(
                    {"detail": "Solo superuser o admin_tienda puede listar tiendas."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Admin ve su tienda principal + sus sucursales + tiendas donde es propietario
            from django.db.models import Q
            tiendas = Tienda.objects.filter(is_deleted=False).filter(
                Q(id=user.tienda.id) | Q(tienda_padre=user.tienda) | Q(propietario=user)  # type: ignore
            ).distinct()
        serializer = TiendaSerializer(tiendas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateTienda(APIView):
    """Superuser + AdminTienda: crear tienda/sucursal"""
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        # Validar que sea superuser o admin_tienda
        is_admin = user.is_superuser or (user.tienda and user.tienda.propietario_id == user.id)  # type: ignore
        if not is_admin:
            return Response(
                {"detail": "Solo superuser o admin_tienda puede crear tiendas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nombre_tienda = request.data.get("nombre")
        if nombre_tienda and Tienda.objects.filter(nombre__iexact=nombre_tienda).exists():
            return Response(
                {"error": f"Ya existe una tienda con el nombre '{nombre_tienda}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        # Si es admin_tienda y no es superuser, forzar que la tienda creada quede vinculada a él
        # - Si crea sucursal (tienda_padre), debe ser su propia tienda
        # - Si crea tienda principal, asignarle como propietario si no viene
        if not user.is_superuser:
            # Sucursal: forzar tienda_padre a su tienda principal si lo intenta crear
            tienda_padre_id = data.get("tienda_padre")
            if tienda_padre_id:
                # Validar que el padre sea su tienda
                if str(tienda_padre_id) != str(user.tienda.id):  # type: ignore
                    return Response(
                        {"error": "Solo puedes crear sucursales de tu propia tienda."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                # Tienda principal: auto-asignar propietario si no viene
                if not data.get("propietario"):
                    data["propietario"] = user.id  # type: ignore
            # Admin no puede elegir otro propietario ni serie libremente (se respeta UpdateTienda restriction, pero aquí también)
            # Permitir serie, pero será validada por serializer

        serializer = TiendaSerializer(data=data)
        if serializer.is_valid():
            tienda = serializer.save()
            # Sucursal: el propietario debe ser el mismo de la tienda padre
            if tienda.tienda_padre and tienda.propietario != tienda.tienda_padre.propietario:
                tienda.propietario = tienda.tienda_padre.propietario
                tienda.save(update_fields=["propietario"])
                serializer = TiendaSerializer(tienda)
            # Asegurar propietario para admin que crea tienda principal sin propietario explícito
            elif not user.is_superuser and tienda.propietario is None and tienda.tienda_padre is None:
                tienda.propietario = user  # type: ignore
                tienda.save(update_fields=["propietario"])
                serializer = TiendaSerializer(tienda)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# SUPERUSER + ADMIN TIENDA: Ver tienda
# ============================================

class GetTienda(APIView):
    """Ver una tienda por ID"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def get(self, request, id):
        tienda = get_object_or_404(Tienda, id=id, is_deleted=False)
        self.check_object_permissions(request, tienda)
        serializer = TiendaSerializer(tienda)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateTienda(APIView):
    """Actualizar tienda"""
    permission_classes = [IsAuthenticated, IsAdminTienda]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        data = request.data.copy()

        if not request.user.is_superuser:
            campos_restringidos = ['serie', 'propietario', 'tienda_padre']
            for campo in campos_restringidos:
                data.pop(campo, None)

        serializer = TiendaSerializer(tienda, data=data, partial=True)
        if serializer.is_valid():
            if 'logo_img' in request.FILES and tienda.logo_img:
                tienda.logo_img.delete(save=False)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeactivateTienda(APIView):
    """Activar/desactivar tienda"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def patch(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)

        activo = request.data.get('activo', None)
        if activo is None:
            return Response(
                {"error": "'activo' es requerido (true o false)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tienda.activo = activo
        tienda.save()

        User.objects.filter(tienda=tienda).update(is_active=activo)

        mensaje = "Tienda activada correctamente" if activo else "Tienda desactivada correctamente"
        return Response({"message": mensaje, "tienda_id": tienda.id, "activo": tienda.activo}, status=status.HTTP_200_OK)


class HabilitarTiendaEliminada(APIView):
    """Habilitar tienda eliminada"""
    permission_classes = [IsAuthenticated, IsAdminTienda]

    def put(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        self.check_object_permissions(request, tienda)
        tienda.is_deleted = False
        tienda.save()
        User.objects.filter(tienda=tienda).update(is_active=True)
        return Response(
            {"message": "Tienda habilitada y usuarios reactivados correctamente."},
            status=status.HTTP_200_OK
        )


# ============================================
# ADMIN TIENDA: Ver mi tienda
# ============================================

class GetMiTiendaView(APIView):
    """Admin tienda: ver mi tienda"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            tiendas = Tienda.objects.filter(is_deleted=False)
            return Response(TiendaSerializer(tiendas, many=True).data, status=status.HTTP_200_OK)

        if not user.tienda:
            return Response(
                {"error": "No tienes tienda asociada"},
                status=status.HTTP_404_NOT_FOUND
            )

        sucursales = Tienda.objects.filter(
            tienda_padre=user.tienda, is_deleted=False
        )
        return Response(
            TiendaSerializer(sucursales, many=True).data,
            status=status.HTTP_200_OK
        )
