from rest_framework import serializers
from apps.inventario.models import Inventario


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.SerializerMethodField()
    tienda_nombre = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()  # Nuevo campo
    categoria_id = serializers.SerializerMethodField()  # ✅ Agregado


    class Meta:
        model = Inventario
        fields = [
            'id', 'producto', 'producto_nombre','categoria_id','categoria_nombre',
            'tienda', 'tienda_nombre',
            'cantidad', 'stock_minimo', 'stock_maximo',
            'costo_compra', 'costo_venta', 'fecha_actualizacion',
            'activo', 'lote', 'fecha_vencimiento', 'estado',
            'proveedor', 'proveedor_nombre',
            'responsable', 
            'descripcion','date_created'
        ]

    def get_producto_nombre(self, obj):
        return obj.producto.nombre if obj.producto else "Desconocido"

    def get_tienda_nombre(self, obj):
        return obj.tienda.nombre if obj.tienda else "Desconocido"

    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else "Desconocido"

    def get_categoria_nombre(self, obj):
        return obj.producto.categoria.nombre if obj.producto and obj.producto.categoria else "Desconocido"
    def get_categoria_id(self, obj):
        return obj.producto.categoria.id if obj.producto and obj.producto.categoria else None