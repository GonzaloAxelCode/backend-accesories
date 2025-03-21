from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from django.shortcuts import get_object_or_404

from apps.cliente.models import Cliente
from apps.cliente.serializers import ClienteSerializer
# Create your views here.
class CreateCliente(APIView):
    def post(self, request):
        serializer = ClienteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetAllClientes(APIView):
    def get(self, request):
        clientes = Cliente.objects.all()
        serializer = ClienteSerializer(clientes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetCliente(APIView):
    def get(self, request, dni):
        cliente = get_object_or_404(Cliente, dni=dni)
        serializer = ClienteSerializer(cliente)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UpdateCliente(APIView):
    def put(self, request, dni):
        cliente = get_object_or_404(Cliente, dni=dni)
        serializer = ClienteSerializer(cliente, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DeactivateCliente(APIView):
    def patch(self, request, dni):
        cliente = get_object_or_404(Cliente, dni=dni)
        cliente.activo = False # type: ignore
        cliente.save()
        return Response({"message": "Cliente desactivado exitosamente"}, status=status.HTTP_200_OK)
