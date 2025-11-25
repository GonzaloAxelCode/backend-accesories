from rest_framework import serializers
from .models import Categoria

class CategoriaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Categoria
        fields = '__all__'

    def validate_caracteristicas_template(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("caracteristicas_template debe ser una lista.")
        return value
