from rest_framework import serializers
from apps.inventario.models import Inventario


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')
    tienda_nombre = serializers.ReadOnlyField(source='tienda.nombre')
    

    class Meta:
        model = Inventario
        fields = [
            'id',
            'producto',
            'producto_nombre',
            'tienda',
            'tienda_nombre',
            'cantidad',
            'stock_minimo',
            'stock_maximo',
            'fecha_actualizacion',
            'activo',
            'lote',
            'fecha_vencimiento',
            'costo',
            'estado'
        ]
