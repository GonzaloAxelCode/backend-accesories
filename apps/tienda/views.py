from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Tienda
from django.contrib.auth import get_user_model
from .serializers import TiendaSerializer
from rest_framework.permissions import IsAuthenticated
User = get_user_model()
class CreateTienda(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if not request.user.is_superuser:
            return Response(
                {"error": "No tienes permisos para realizar esta acción."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 🔹 Validar si ya existe una tienda con el mismo nombre
        nombre_tienda = request.data.get("nombre")
        if Tienda.objects.filter(nombre__iexact=nombre_tienda).exists():
            return Response(
                {"error": f"Ya existe una tienda con el nombre '{nombre_tienda}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TiendaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# Obtener todas las tiendas
class GetAllTiendas(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if not request.user.is_superuser:
            return Response({"error": "No tienes permisos para realizar esta acción."}, status=status.HTTP_403_FORBIDDEN)

        tiendas = Tienda.objects.all()
        serializer = TiendaSerializer(tiendas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Obtener una tienda por ID
class GetTienda(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        serializer = TiendaSerializer(tienda)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Actualizar una tienda por ID
class UpdateTienda(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, id):
        if not request.user.is_superuser:
            return Response({"error": "No tienes permisos para realizar esta acción."}, status=status.HTTP_403_FORBIDDEN)

        tienda = get_object_or_404(Tienda, id=id)
        serializer = TiendaSerializer(tienda, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeactivateTienda(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        if not request.user.is_superuser:
            return Response(
                {"error": "No tienes permisos para realizar esta acción."},
                status=status.HTTP_403_FORBIDDEN
            )

        tienda = get_object_or_404(Tienda, id=id)
        activo = request.data.get('activo', None)

        if activo is None:
            return Response(
                {"error": "'activo' es requerido (true o false)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 Actualizar estado de la tienda
        tienda.activo = activo
        tienda.save()

        # 🔹 Actualizar todos los usuarios asociados a la tienda
        usuarios_actualizados = User.objects.filter(tienda=tienda)
        usuarios_actualizados.update(is_active=activo)

        # 🔹 Mensaje contextual
        mensaje = (
            "Tienda y usuarios activados correctamente"
            if activo else
            "Tienda y usuarios desactivados correctamente"
        )

        return Response(
            {"message": mensaje, "tienda_id": tienda.id, "activo": tienda.activo}, # type: ignore
            status=status.HTTP_200_OK
        )