from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Tienda
from .serializers import TiendaSerializer

# Crear una nueva tienda
class CreateTienda(APIView):
    def post(self, request):
        serializer = TiendaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Obtener todas las tiendas
class GetAllTiendas(APIView):
    def get(self, request):
        tiendas = Tienda.objects.all()
        serializer = TiendaSerializer(tiendas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Obtener una tienda por ID
class GetTienda(APIView):
    def get(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        serializer = TiendaSerializer(tienda)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Actualizar una tienda por ID
class UpdateTienda(APIView):
    def put(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        serializer = TiendaSerializer(tienda, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Desactivar una tienda por ID
class DeactivateTienda(APIView):
    def patch(self, request, id):
        tienda = get_object_or_404(Tienda, id=id)
        tienda.activo = False
        tienda.save()
        return Response({"message": "Tienda desactivada exitosamente"}, status=status.HTTP_200_OK)
