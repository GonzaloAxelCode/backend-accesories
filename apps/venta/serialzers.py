

from rest_framework import serializers
from .models import Venta, DetalleVenta
from apps.producto.models import Producto

class DetalleVentaSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = DetalleVenta
        fields = '__all__'
class VentaSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = Venta
        fields = '__all__'
