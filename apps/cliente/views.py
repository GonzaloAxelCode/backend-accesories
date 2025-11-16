from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from apps.cliente.models import Cliente
from apps.cliente.serializers import ClienteSerializer
# Create your views here.
class CreateCliente(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request):
        try:
            tienda = getattr(request.user, "tienda", None)
            
            if not tienda:
                return Response(
                    {"error": "El usuario no tiene una tienda asignada."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            dni = request.data.get("dni")
            
            # Verificar si ya existe un cliente con ese DNI en esta tienda
            if dni and Cliente.objects.filter(dni=dni, tienda=tienda).exists():
                return Response(
                    {
                        "error": "Ya existe un cliente con este DNI en esta tienda.",
                       
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = ClienteSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(tienda=tienda)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetAllClientes(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        clientes = Cliente.objects.filter(tienda=tienda)
        serializer = ClienteSerializer(clientes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetCliente(APIView):
    def get(self, request, dni):
        tienda = getattr(request.user, "tienda", None)
        cliente = get_object_or_404(Cliente, dni=dni,tienda=tienda),
        serializer = ClienteSerializer(cliente)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DeactivateCliente(APIView):
    def patch(self, request, dni):
        cliente = get_object_or_404(Cliente, dni=dni)
        cliente.activo = False # type: ignore
        cliente.save()
        return Response({"message": "Cliente desactivado exitosamente"}, status=status.HTTP_200_OK)
