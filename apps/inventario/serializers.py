from rest_framework import serializers
from apps.inventario.models import Inventario


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')
    tienda_nombre = serializers.ReadOnlyField(source='tienda.nombre')
    

    class Meta:
        model = Inventario
        fields = '__all__'  # Incluir todos los campos
