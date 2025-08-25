# apps/tienda/serializers.py
from rest_framework import serializers

from apps.user.serializers import UserSerializer
from .models import Tienda


class TiendaSerializer(serializers.ModelSerializer):
    encargado = UserSerializer(read_only=True)   # OneToOne
    users_tienda = UserSerializer(many=True, read_only=True)  # FK reverse relation

    class Meta:
        model = Tienda
        fields = [
            "id",
            "nombre",
            "direccion",
            "ciudad",
            "telefono",
            "activo",
            "encargado",
            "capacidad",
            "ruc",
            "imagen",
            "users_tienda",  # 👈 añadimos lista de usuarios
        ]
