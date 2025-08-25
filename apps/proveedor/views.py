from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.inventario.models import Inventario
from apps.proveedor.models import Proveedor
from apps.proveedor.serializers import ProveedorSerializer


class CreateProveedor(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProveedorSerializer(data=request.data)

        # Tomar la tienda desde el usuario autenticado
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"detail": "El usuario no tiene una tienda asociada."}, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            # Asignar la tienda antes de guardar
            serializer.save(tienda=tienda)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetAllProveedores(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"detail": "El usuario no tiene una tienda asociada."}, status=status.HTTP_400_BAD_REQUEST)

        proveedores = Proveedor.objects.filter(tienda=tienda)
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GetProveedor(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)
        serializer = ProveedorSerializer(proveedor)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateProveedor(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)
        serializer = ProveedorSerializer(proveedor, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteProveedor(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)
        proveedor.delete()
        return Response({"message": "Proveedor eliminado exitosamente"}, status=status.HTTP_204_NO_CONTENT)


class ToggleCanActiveProveedor(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)

        # Obtener el parámetro "activo" del body del POST
        activo = request.data.get("activo", True)  # por defecto True si no envías
        proveedor.activo = bool(activo)
        proveedor.save()

        # Actualizar inventarios relacionados
        Inventario.objects.filter(proveedor=proveedor).update(activo=bool(activo))

        mensaje = (
            "Proveedor activado y sus inventarios activos"
            if activo else
            "Proveedor desactivado y sus inventarios inactivos"
        )

        return Response({"message": mensaje}, status=status.HTTP_200_OK)
