from rest_framework import serializers
from .models import Producto


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.SerializerMethodField()
    imagen = serializers.ImageField(required=False, allow_null=True)  # 👈 Hacer opcional

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
            'imagen'  # 👈 Campo de imagen
        ]
        extra_kwargs = {
            'imagen': {'required': False}  # 👈 No obligatorio en actualizaciones
        }

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else "Sin categoria"
    
    def update(self, instance, validated_data):
        # Si se envía una nueva imagen, eliminar la anterior (opcional)
        if 'imagen' in validated_data and validated_data['imagen']:
            if instance.imagen:
                # Eliminar archivo anterior del sistema de archivos
                instance.imagen.delete(save=False)
        
        return super().update(instance, validated_data)