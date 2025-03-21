

from rest_framework import serializers
from .models import Venta
from apps.producto.models import Producto


class VentaSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = Venta
        fields = '__all__'
