from rest_framework import serializers
from apps.compras.models import ComprobanteCompra

class ComprobanteCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComprobanteCompra
        fields = '__all__'
