from rest_framework import serializers
from apps.inventario.models import Inventario


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.SerializerMethodField()
    tienda_nombre = serializers.SerializerMethodField()
    proveedor_nombre = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()  # Nuevo campo
    producto_sku = serializers.SerializerMethodField()  # Nuevo campo
    categoria_id = serializers.SerializerMethodField()  # ✅ Agregado
    imagen_producto = serializers.SerializerMethodField()
    repuesto_tipo = serializers.SerializerMethodField()
    item_nombre = serializers.SerializerMethodField()
    producto_marca = serializers.SerializerMethodField()
    producto_modelo = serializers.SerializerMethodField()
    categoria_tipo = serializers.SerializerMethodField()

    class Meta:
        model = Inventario
        fields = [
            'id', 'producto', 'repuesto', 'repuesto_tipo', 'item_nombre',
            'producto_nombre','producto_sku','producto_marca','producto_modelo',
            'categoria_id','categoria_nombre','categoria_tipo','imagen_producto',
            'tienda', 'tienda_nombre',
            'cantidad', 'stock_minimo', 'stock_maximo',
            'costo_compra', 'costo_venta', 'fecha_actualizacion',
            'activo', 'lote', 'fecha_vencimiento', 'estado',
            'proveedor', 'proveedor_nombre', 'ubicacion',
            'responsable', 
            'descripcion','date_created'
        ]

    def get_producto_nombre(self, obj):
        return obj.producto.nombre if obj.producto else "Desconocido"
    def get_producto_sku(self, obj):
        return obj.producto.sku if obj.producto else "Desconocido"


    def get_tienda_nombre(self, obj):
        return obj.tienda.nombre if obj.tienda else "Desconocido"

    def get_proveedor_nombre(self, obj):
        return obj.proveedor.nombre if obj.proveedor else None

    def get_repuesto_tipo(self, obj):
        if not obj.repuesto:
            return None
        cat = getattr(obj.repuesto, "categoria", None)
        return cat.nombre if cat else None

    def get_item_nombre(self, obj):
        if obj.producto:
            return obj.producto.nombre
        if obj.repuesto:
            return obj.repuesto.nombre or obj.repuesto.modelos_compatibles
        return "Desconocido"

    def get_categoria_nombre(self, obj):
        return obj.producto.categoria.nombre if obj.producto and obj.producto.categoria else "Desconocido"
    def get_categoria_id(self, obj):
        return obj.producto.categoria.id if obj.producto and obj.producto.categoria else None
    def get_producto_marca(self, obj):
        if obj.producto and getattr(obj.producto, "marca", None):
            return (obj.producto.marca or "").strip() or None
        return None
    def get_producto_modelo(self, obj):
        if obj.producto and getattr(obj.producto, "modelo", None):
            return (obj.producto.modelo or "").strip() or None
        return None
    def get_categoria_tipo(self, obj):
        if obj.producto and getattr(obj.producto, "categoria", None):
            return getattr(obj.producto.categoria, "tipo", None)
        if obj.repuesto and getattr(obj.repuesto, "categoria", None):
            return getattr(obj.repuesto.categoria, "tipo", None)
        return None
    def get_imagen_producto(self, obj):
        
        if obj.producto and obj.producto.imagen:
            request = self.context.get('request')
            imagen_url = obj.producto.imagen.url
            return request.build_absolute_uri(imagen_url) if request else imagen_url
        return None