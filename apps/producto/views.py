from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Producto
from .serializers import ProductoSerializer

# Obtener todos los productos
class GetAllProductosAPIView(APIView):
    def get(self, request):
        productos = Producto.objects.all()
        serializer = ProductoSerializer(productos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Obtener un solo producto
class GetProductoAPIView(APIView):
    def get(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        serializer = ProductoSerializer(producto)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Crear un nuevo producto
class CreateProductoAPIView(APIView):
    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Producto creado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Actualizar un producto
class UpdateProductoAPIView(APIView):
    def put(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        serializer = ProductoSerializer(producto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Producto actualizado exitosamente",
                "producto": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Eliminar un producto
class DeleteProductoAPIView(APIView):
    def delete(self, request, id):
        producto = get_object_or_404(Producto, id=id)
        producto.delete()
        return Response({
            "message": "Producto eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)
