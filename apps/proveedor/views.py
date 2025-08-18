from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps import tienda
from apps.inventario.models import Inventario
from apps.proveedor.models import Proveedor
from apps.proveedor.serializers import ProveedorSerializer
from apps.tienda.models import Tienda

# Create your views here.
class CreateProveedor(APIView):
    def post(self, request):
        data = request.data 
        serializer = ProveedorSerializer(data=request.data)
        
        tienda = get_object_or_404(Tienda, id=data.get("tienda"))
        if serializer.is_valid():
            # Asignar la tienda al proveedor antes de guardar
            
            serializer.save(tienda=tienda)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetAllProveedores(APIView):
    def get(self, request):
        tienda = request.query_params.get('tienda')
        proveedores = Proveedor.objects.filter(tienda=tienda) 
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

class DeleteProveedor(APIView):
    def delete(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id)
        proveedor.delete()

        return Response({"message": "Proveedor eliminado exitosamente"}, status=status.HTTP_204_NO_CONTENT)
# Desactivar proveedor
class ToggleCanActiveProveedor(APIView):
    def post(self, request, id):
        proveedor = get_object_or_404(Proveedor, id=id)
        
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