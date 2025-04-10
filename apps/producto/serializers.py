from rest_framework import serializers
from .models import Producto

class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [  # Incluye solo los campos necesarios
            'id', 
            'nombre', 
            'descripcion', 
            'categoria',  # Campo de relación (ID de la categoría)
            'categoria_nombre',  # ¡Asegúrate de agregarlo aquí!
            'sku', 
            'marca', 
            'modelo', 
            'caracteristicas',
            'fecha_creacion', 
            'fecha_actualizacion', 
            'activo'
        ]

    def get_categoria_nombre(self, obj):
        # Verifica si existe la categoría y devuelve su nombre
        return obj.categoria.nombre if obj.categoria else "Sin categoria"