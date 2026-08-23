from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta, date
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
            
            document = request.data.get("document")
            
            if document and Cliente.objects.filter(document=document, tienda=tienda).exists():
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
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

class GetCliente(APIView):
    def get(self, request, document):
        tienda = getattr(request.user, "tienda", None)
        cliente = get_object_or_404(Cliente, document=document, tienda=tienda)
        serializer = ClienteSerializer(cliente)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DeactivateCliente(APIView):
    def patch(self, request, document):
        cliente = get_object_or_404(Cliente, document=document)
        cliente.activo = False # type: ignore
        cliente.save()
        return Response({"message": "Cliente desactivado exitosamente"}, status=status.HTTP_200_OK)


class ResumenClientesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tienda = getattr(request.user, "tienda", None)
        if not tienda:
            return Response(
                {"error": "El usuario no tiene una tienda asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        hoy = timezone.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)

        total = Cliente.objects.filter(tienda=tienda).count()
        nuevos_hoy = Cliente.objects.filter(tienda=tienda, date_created__date=hoy).count()
        nuevos_semana = Cliente.objects.filter(tienda=tienda, date_created__date__gte=inicio_semana).count()
        nuevos_mes = Cliente.objects.filter(tienda=tienda, date_created__date__gte=inicio_mes).count()

        return Response({
            "total_clientes": total,
            "nuevos_hoy": nuevos_hoy,
            "nuevos_semana": nuevos_semana,
            "nuevos_mes": nuevos_mes
        }, status=status.HTTP_200_OK)
