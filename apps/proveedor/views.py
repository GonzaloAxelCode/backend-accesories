from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.proveedor.models import Proveedor
from apps.proveedor.serializers import ProveedorSerializer

# Create your views here.
class CreateProveedor(APIView):
    def post(self, request):
        serializer = ProveedorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetAllProveedores(APIView):
    def get(self, request):
        proveedores = Proveedor.objects.all()
        serializer = ProveedorSerializer(proveedores, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetProveedor(APIView):
    def get(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id)
        serializer = ProveedorSerializer(proveedor)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UpdateProveedor(APIView):
    def put(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id)
        serializer = ProveedorSerializer(proveedor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DeactivateProveedor(APIView):
    def patch(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id)
        proveedor.activo = False
        proveedor.save()
        return Response({"message": "Proveedor desactivado exitosamente"}, status=status.HTTP_200_OK)
