from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.proveedor.models import Proveedor
from apps.proveedor.serializers import ProveedorSerializer
from core.permissions import CanCreateProveedorPermission, CanUpdateProveedorPermission


class CreateProveedor(APIView):
    permission_classes = [IsAuthenticated, CanCreateProveedorPermission]

    def post(self, request):
        serializer = ProveedorSerializer(data=request.data, context={'request': request})

        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response({"detail": "El usuario no tiene una tienda asociada."}, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
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


class UpdateProveedor(APIView):
    permission_classes = [IsAuthenticated, CanUpdateProveedorPermission]

    def put(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)
        serializer = ProveedorSerializer(proveedor, data=request.data, partial=True, context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ToggleActivarProveedor(APIView):
    permission_classes = [IsAuthenticated, CanUpdateProveedorPermission]

    def put(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id, tienda=request.user.tienda)

        activar = request.data.get("activo", True)

        if activar:
            proveedor.activo = True
            proveedor.save()
            return Response({
                "message": "Proveedor activado exitosamente",
                "id": proveedor.id,
                "ruc": proveedor.ruc,
                "activo": proveedor.activo,
            }, status=status.HTTP_200_OK)
        else:
            proveedor.ruc = f"{proveedor.ruc}-{proveedor.id}"
            proveedor.activo = False
            proveedor.save()

            return Response({
                "message": "Proveedor desactivado exitosamente",
                "id": proveedor.id,
                "ruc": proveedor.ruc,
                "activo": proveedor.activo,
            }, status=status.HTTP_200_OK)
