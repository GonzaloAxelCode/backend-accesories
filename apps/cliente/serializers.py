from rest_framework.views import APIView
from rest_framework import serializers

from apps.cliente.models import Cliente

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'
