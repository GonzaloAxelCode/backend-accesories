# serializers.py

from rest_framework import serializers
from apps.caja.models import Caja, OperacionCaja

class CajaSerializer(serializers.ModelSerializer):
    # Si hay campos numéricos, puedes especificar explícitamente el tipo
    saldo_inicial = serializers.DecimalField(max_digits=10, decimal_places=2)
    saldo_final = serializers.DecimalField(max_digits=10, decimal_places=2)
    ingresos = serializers.DecimalField(max_digits=10, decimal_places=2)
    egresos = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Caja
        fields = '__all__'


class OperacionCajaSerializer(serializers.ModelSerializer):
    # Asegúrate de que los campos numéricos no se serialicen como cadenas
    monto = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = OperacionCaja
        fields = '__all__'
