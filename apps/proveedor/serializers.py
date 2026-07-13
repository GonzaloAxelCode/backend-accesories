from rest_framework import serializers
from .models import Proveedor


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = '__all__'
        read_only_fields = ['tienda']

    def validate_ruc(self, value):
        tienda = self.context['request'].user.tienda
        proveedor_id = self.instance.id if self.instance else None

        exists = Proveedor.objects.filter(
            ruc=value,
            tienda=tienda,
            activo=True,
        ).exclude(id=proveedor_id).exists()

        if exists:
            raise serializers.ValidationError("Ya existe un proveedor activo con este RUC en esta tienda.")
        return value

    def validate_nombre(self, value):
        tienda = self.context['request'].user.tienda
        proveedor_id = self.instance.id if self.instance else None

        exists = Proveedor.objects.filter(
            nombre=value,
            tienda=tienda,
            activo=True,
        ).exclude(id=proveedor_id).exists()

        if exists:
            raise serializers.ValidationError("Ya existe un proveedor activo con este nombre en esta tienda.")
        return value
