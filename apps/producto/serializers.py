from rest_framework import serializers
from .models import Producto
import json

class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.SerializerMethodField()
    imagen = serializers.ImageField(required=False, allow_null=True)
    is_inventario = serializers.SerializerMethodField()
    inventario = serializers.SerializerMethodField()

    # 👇 Aseguramos que caracteristicas sea JSON válido
    caracteristicas = serializers.JSONField(required=False)

    class Meta:
        model = Producto
        fields = [
            'id',
            'nombre',
            'descripcion',
            'categoria',
            'categoria_nombre',
            'sku',
            'marca',
            'modelo',
            'caracteristicas',
            'fecha_creacion',
            'fecha_actualizacion',
            'activo',
            'imagen',
            'is_inventario',
            'inventario',
        ]

    # ------------------------
    # 🚀 CAMPOS EXTRA
    # ------------------------

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else "Sin categoria"

    def get_is_inventario(self, obj):
        from apps.inventario.models import Inventario  
        return Inventario.objects.filter(producto=obj).exists()

    def get_inventario(self, obj):
        from apps.inventario.models import Inventario
        from apps.inventario.serializers import InventarioSerializer
        
        inventario = Inventario.objects.filter(producto=obj).first()
        return InventarioSerializer(inventario).data if inventario else None

    # ------------------------
    # 🧹 VALIDACIÓN caracteristicas
    # ------------------------

       # ------------------------
    # 🖼️ Manejo de imagen
    # ------------------------

    def validate_nombre(self, value):
        tienda = None
        request = self.context.get("request")
        if request:
            tienda = getattr(request.user, "tienda", None)

        if not tienda:
            raise serializers.ValidationError("No se pudo determinar la tienda del usuario.")

        qs = Producto.objects.filter(nombre__iexact=value, tienda=tienda, activo=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Ya existe un producto con este nombre en la tienda.")

        return value

    def update(self, instance, validated_data):
        # Si se sube nueva imagen, borrar la anterior
        if 'imagen' in validated_data and validated_data['imagen']:
            if instance.imagen:
                instance.imagen.delete(save=False)

        return super().update(instance, validated_data)


class ProductoDetalleCompletoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.SerializerMethodField()
    imagen = serializers.ImageField(required=False, allow_null=True)
    is_inventario = serializers.SerializerMethodField()
    inventarios = serializers.SerializerMethodField()
    tienda_nombre = serializers.SerializerMethodField()

    # 👇 Aseguramos que caracteristicas sea JSON válido
    caracteristicas = serializers.JSONField(required=False)

    class Meta:
        model = Producto
        fields = [
            'id',
            'nombre',
            'descripcion',
            'categoria',
            'categoria_nombre',
            'sku',
            'marca',
            'modelo',
            'caracteristicas',
            'fecha_creacion',
            'fecha_actualizacion',
            'activo',
            'imagen',
            'is_inventario',
            'inventarios',
            'tienda',
            'tienda_nombre',
        ]

    # ------------------------
    # 🚀 CAMPOS EXTRA
    # ------------------------

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else "Sin categoria"

    def get_tienda_nombre(self, obj):
        return obj.tienda.nombre if obj.tienda else "Sin tienda"

    def get_is_inventario(self, obj):
        from apps.inventario.models import Inventario  
        return Inventario.objects.filter(producto=obj).exists()

    def get_inventarios(self, obj):
        from apps.inventario.models import Inventario
        from apps.inventario.serializers import InventarioSerializer
        
        inventarios = Inventario.objects.filter(producto=obj, activo=True)
        return InventarioSerializer(inventarios, many=True).data if inventarios.exists() else []
