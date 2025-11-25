from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.categoria.serializers import CategoriaSerializer
from apps.tienda.models import Tienda
from core.permissions import CanCreateCategoryPermission, CanDeleteCategoryPermission, CanModifyCategoryPermission
from .models import Categoria


# Crear una nueva categoria
class CreateCategoria(APIView):
    permission_classes = [IsAuthenticated, CanCreateCategoryPermission]

    def post(self, request):
        data = request.data.copy()

        # Si no viene `caracteristicas_template`, lo forzamos a lista vacía
        if "caracteristicas_template" not in data:
            data["caracteristicas_template"] = []

        tienda = request.user.tienda

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
        categorias = Categoria.objects.filter(tienda=tienda,activo=True) 
        serializer = CategoriaSerializer(categorias, many=True,)
        print(serializer.data)
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
    permission_classes = [IsAuthenticated,CanModifyCategoryPermission]    
    def put(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        serializer = CategoriaSerializer(categoria, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Desactivar una categoria por ID
class DeactivateCategoria(APIView):
    
    permission_classes = [IsAuthenticated,CanDeleteCategoryPermission]    
    def patch(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        categoria.activo = False
        categoria.nombre = f"{categoria.nombre}(Delete)_{categoria.id}" # type: ignore
        categoria.save()
        return Response({"message": "Categoria desactivada exitosamente"}, status=status.HTTP_200_OK)
class DeleteCategoria(APIView):
    permission_classes = [IsAuthenticated,CanDeleteCategoryPermission]    
    def delete(self, request, id):
        categoria = get_object_or_404(Categoria, id=id)
        categoria.activo = False
        categoria.nombre = f"{categoria.nombre}(Delete)_{categoria.id}" # type: ignore
        categoria.save()
        return Response({"message": "Categoria eliminada exitosamente"}, status=status.HTTP_204_NO_CONTENT)
