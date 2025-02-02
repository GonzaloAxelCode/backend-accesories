from rest_framework.views import APIView
from rest_framework import serializers

from apps.cliente.models import Cliente

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'

class ClienteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'dni', 'email', 'telefono', 'direccion', 'pais', 'codigo_postal', 'fecha_nacimiento', 'genero']

class ClienteUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'telefono', 'direccion', 'pais', 'codigo_postal', 'fecha_nacimiento', 'genero']

class ClienteDeactivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['activo']
