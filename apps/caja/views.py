from decimal import Decimal
from django.shortcuts import get_object_or_404, render

# Create your views here.
# views.py
from datetime import datetime, timedelta
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import now
from django.db.models import Q
from apps import tienda
from apps.caja.models import Caja, OperacionCaja
from apps.caja.serializers import CajaSerializer, OperacionCajaSerializer
from django.contrib.auth import get_user_model
User = get_user_model()
class CajaAbiertaView(APIView):
    def get(self, request):
        tienda_id =request.user.tienda

        try:
            caja = Caja.objects.get(
                tienda_id=tienda_id,
                estado='abierta',
                
            )
        except Caja.DoesNotExist:
            return Response({
                "caja_is_open": False,
                "caja": {},
                "operaciones": [],
                "message": "No hay cajas abiertas para esta tienda hoy."
            }, status=status.HTTP_200_OK)

        operaciones = OperacionCaja.objects.filter(caja=caja)
        caja_data = CajaSerializer(caja).data
        operaciones_data = OperacionCajaSerializer(operaciones, many=True).data

        return Response({
            "caja_is_open": True,
            "caja": caja_data,
            "operaciones": operaciones_data
        }, status=status.HTTP_200_OK)


class IniciarCajaView(APIView):
    def post(self, request, *args, **kwargs):
        tienda_id =request.user.tienda
       
        usuario_id = request.user.id
        saldo_inicial = request.data.get('saldo_inicial')
        print(tienda_id , usuario_id, saldo_inicial)
        # Validar que los campos necesarios están presentes
        if not tienda_id or not usuario_id or saldo_inicial is None:
            return Response({
                "message": "Faltan datos requeridos. Asegúrate de enviar 'tienda_id', 'usuario_id' y 'saldo_inicial'."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Obtener la instancia del usuario con el id proporcionado
        usuario_apertura = get_object_or_404(User, id=usuario_id)
        
        # Verificamos si ya existe una caja abierta para la tienda (sin importar el día)
        try:
            caja_abierta = Caja.objects.get(tienda_id=tienda_id, estado='abierta')
            
            # Si la caja está abierta, no podemos abrir una nueva
            return Response({
                "caja_is_open": True,
                "message": "Ya existe una caja abierta para esta tienda.",
                "caja": {},
                "operaciones":[]
            }, status=status.HTTP_400_BAD_REQUEST)

        except Caja.DoesNotExist:
            
            # Si no existe una caja abierta, creamos una nueva caja
            caja = Caja.objects.create(
                tienda=tienda_id,
                fecha_apertura= timezone.make_aware(datetime.now()),
                usuario_apertura=usuario_apertura,
                saldo_inicial=saldo_inicial,
                saldo_final=saldo_inicial,  # Inicialmente igual al saldo inicial
                estado='abierta'
                
            )

            # Obtenemos las operaciones de la caja (aunque probablemente estará vacía al principio)
            operaciones = OperacionCaja.objects.filter(caja=caja)
            caja_data = CajaSerializer(caja).data
            operaciones_data = OperacionCajaSerializer(operaciones, many=True).data

            # Retornamos una respuesta exitosa con la estructura solicitada
            return Response({
                "caja_is_open": True,
                "caja": caja_data,
                "operaciones": operaciones_data
            }, status=status.HTTP_201_CREATED)
        except Exception as e: 
            return Response({
                "message": f"Error al iniciar la caja: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RealizarGastoView(APIView):
    def post(self, request):
        caja_id = request.data.get("caja_id")
        monto = request.data.get("monto")
        tienda_id =request.user.tienda
        descripcion = request.data.get("descripcion", "")
        usuario_id = request.user.id

        if not caja_id or not monto or not usuario_id:
            return Response({"message": "Faltan datos requeridos."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            caja = Caja.objects.get(id=caja_id, estado="abierta",tienda_id=tienda_id)
        except Caja.DoesNotExist:
            return Response({"message": "No hay caja abierta para esta tienda."}, status=status.HTTP_400_BAD_REQUEST)

        # Validar que el saldo sea suficiente
        if Decimal(caja.saldo_final) < Decimal(monto): # type: ignore
            return Response({
                "message": "El gasto excede el saldo disponible en caja chica."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Crear la operación de gasto
        operacion = OperacionCaja.objects.create(
            caja=caja,
            tipo="gasto",  # Asegúrate que este valor sea válido para el campo tipo
            monto=monto,
            detalles=descripcion,
            usuario_id=usuario_id,
            fecha= timezone.make_aware(datetime.now())
        )

        # Actualizar el saldo final de la caja
        caja.saldo_final -= Decimal(monto) # type: ignore
        caja.egresos += Decimal(monto) # type: ignore
        caja.save()

        return Response({
            "message": "Gasto registrado correctamente.",
            "operacion": OperacionCajaSerializer(operacion).data,
            "caja":CajaSerializer(caja).data, 
        }, status=status.HTTP_201_CREATED)



class RealizarIngresoView(APIView):
    def post(self, request, *args, **kwargs):
        caja_id = request.data.get("caja_id")
        usuario_id = request.user.id
        monto = request.data.get("monto")
        descripcion = request.data.get("descripcion", "")
        tienda_id =request.user.tienda
        if not caja_id or not usuario_id or monto is None:
            return Response({
                "message": "Faltan datos requeridos: 'tienda_id', 'usuario_id' y 'monto' son obligatorios."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            caja = Caja.objects.get(id=caja_id, estado="abierta",tienda_id=tienda_id)
        except Caja.DoesNotExist:
            return Response({
                "message": "No hay una caja abierta actualmente para esta tienda."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Sumamos el ingreso al saldo final
        caja.saldo_final += Decimal(monto) # type: ignore
        caja.ingresos += Decimal(monto) # type: ignore
        caja.save()

        operacion = OperacionCaja.objects.create(
            caja=caja,
            tipo="ingreso",
            monto=monto,
            fecha=timezone.make_aware(datetime.now()),
            detalles=descripcion,
            usuario_id=usuario_id
        )

        return Response({
            "message": "Ingreso registrado correctamente.",
            "caja": CajaSerializer(caja).data,
            "operacion": OperacionCajaSerializer(operacion).data
        }, status=status.HTTP_201_CREATED)
        

class RegistrarPrestamoView(APIView):
    def post(self, request, *args, **kwargs):
        tienda_id = request.data.get("tienda_id")
        usuario_id = request.user.id
        monto = request.data.get("monto")
        caja_id = request.data.get("caja_id")
        descripcion = request.data.get("descripcion", "")
        tienda_id =request.user.tienda
        if not tienda_id or not usuario_id or monto is None:
            return Response({
                "message": "Faltan datos requeridos: 'tienda_id', 'usuario_id' y 'monto' son obligatorios."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            caja = Caja.objects.get(id=caja_id,tienda_id=tienda_id, estado="abierta",)
        except Caja.DoesNotExist:
            return Response({
                "message": "No hay una caja abierta actualmente para esta tienda."
            }, status=status.HTTP_400_BAD_REQUEST)

        monto = float(monto)
        if monto > caja.saldo_final: # type: ignore
            return Response({
                "message": "No se puede realizar el préstamo. El monto excede el saldo actual de la caja."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Restamos el préstamo del saldo final
        caja.saldo_final -= monto # type: ignore
        caja.save()
        
        operacion = OperacionCaja.objects.create(
            caja=caja,
            tipo="prestamo",
            monto=monto,
            fecha=timezone.make_aware(datetime.now()),
            detalles=descripcion,
            usuario_id=usuario_id
        )

        return Response({
            "message": "Préstamo registrado correctamente.",
            "caja": CajaSerializer(caja).data,
            "operacion": OperacionCajaSerializer(operacion).data,
        }, status=status.HTTP_201_CREATED)


class CerrarCajaView(APIView):
    def post(self, request):
        caja_id = request.data.get("caja_id")
        usuario_id = request.user.id  # usuario que está cerrando la caja
        tienda_id = request.user.tienda
        if not caja_id or not usuario_id:
            return Response({
                "message": "Faltan datos requeridos: 'tienda_id' y 'usuario_id' son obligatorios."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            caja = Caja.objects.get(id=caja_id, estado="abierta",tienda_id=tienda_id)
        except Caja.DoesNotExist:
            return Response({
                "message": "No hay una caja abierta actualmente para esta tienda."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            usuario = User.objects.get(pk=usuario_id)
        except User.DoesNotExist:
            return Response({
                "message": "Usuario no encontrado."
            }, status=status.HTTP_404_NOT_FOUND)

        caja.estado = "cerrada"
        caja.fecha_cierre =  timezone.make_aware(datetime.now())
        caja.usuario_cierre = usuario
        caja.save()

        return Response({
            "message": "Caja cerrada correctamente.",
              "caja_is_open": False,
            "caja": {},
            "operaciones": []
        }, status=status.HTTP_200_OK)

class ReinicializarCajaView(APIView):
    def post(self, request):
        tienda_id = request.user.tienda
      
        caja_id = request.data.get("caja_id")
        usuario_id = request.user.id
        nuevo_saldo = request.data.get("saldo_inicial")

        if not caja_id or not usuario_id or nuevo_saldo is None:
            return Response({
                "message": "Faltan datos: 'tienda_id', 'usuario_id' y 'saldo_inicial' son obligatorios."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Cancelar caja actual si está abierta
            caja_actual = Caja.objects.get(id=caja_id, estado="abierta",tienda_id=tienda_id)
            caja_actual.estado = "cancelada"
            caja_actual.fecha_reinicio = timezone.make_aware(datetime.now())
            caja_actual.save()
        except Caja.DoesNotExist:
            pass  # No hay caja abierta, continuamos

        try:
            usuario = User.objects.get(pk=usuario_id)
        except User.DoesNotExist:
            return Response({"message": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Crear nueva caja
        nueva_caja = Caja.objects.create(
            tienda_id=tienda_id,
            usuario_apertura=usuario,
            fecha_apertura= timezone.make_aware(datetime.now()),
            saldo_inicial=nuevo_saldo,
            saldo_final=nuevo_saldo,
            estado="abierta"
        )
        caja_data = CajaSerializer(nueva_caja).data
        operaciones_data = [] 
        return Response({
            "message": "Caja reinicializada correctamente.",
           "caja_is_open": True,
            "caja": caja_data,
            "operaciones": operaciones_data,
        }, status=status.HTTP_201_CREATED)
        
