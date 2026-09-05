# apps/tienda/serializers.py
from rest_framework import serializers

from apps.user.models import UserAccount
from apps.user.serializers import UserSerializer
from .models import Tienda


class PropietarioDataSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "photo_url",
            "is_active",
            "es_empleado",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class TiendaSerializer(serializers.ModelSerializer):

    users_tienda = UserSerializer(many=True, read_only=True)
    propietario_data = PropietarioDataSerializer(source="propietario", read_only=True)

    class Meta:
        model = Tienda
        fields = '__all__'
        extra_kwargs = {
            'cert_clave_privada': {'write_only': True},
        }

    def validate_nombre(self, value):
        qs = Tienda.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una tienda con este nombre.")
        return value

    def _enrich_user(self, user_data, instance, all_permissions):
        try:
            user_obj = UserAccount.objects.get(id=user_data["id"])
        except UserAccount.DoesNotExist:
            return None

        user_permissions_full = user_obj.get_all_permissions()
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]
        permissions_dict = {
            perm: perm in user_permission_codenames for perm in all_permissions
        }
        user_data["permissions"] = permissions_dict
        user_data["user_permissions_list"] = user_permission_codenames
        user_data["all_permissions_meta"] = all_permissions
        user_data["tienda_nombre"] = instance.nombre
        return user_data

    def _build_propietario_data(self, instance, all_permissions):
        propietario = instance.propietario
        if not propietario:
            return None

        propietario_serialized = PropietarioDataSerializer(propietario).data
        user_permissions_full = propietario.get_all_permissions()
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]
        propietario_serialized["permissions"] = {
            perm: perm in user_permission_codenames for perm in all_permissions
        }
        propietario_serialized["user_permissions_list"] = user_permission_codenames
        propietario_serialized["all_permissions_meta"] = all_permissions
        propietario_serialized["tienda_nombre"] = instance.nombre
        return propietario_serialized

    def to_representation(self, instance):
        data = super().to_representation(instance)

        ALL_PERMISSIONS = [
            "can_make_sale", "can_cancel_sale",
            "can_create_inventory", "can_modify_inventory",
            "can_update_inventory", "can_delete_inventory",
            "can_create_product", "can_update_product", "can_delete_product",
            "can_create_category", "can_modify_category", "can_delete_category",
            "can_create_supplier", "can_modify_supplier", "can_delete_supplier",
            "can_create_store", "can_modify_store", "can_delete_store",
            "view_sale", "view_inventory", "view_product",
            "view_category", "view_supplier", "view_store",
            "can_create_user",
            "can_create_proveedor", "can_update_proveedor", "can_delete_proveedor",
        ]

        request = self.context.get("request")
        if request and request.user and request.user.is_superuser:
            data["sol_password"] = instance.sol_password

        enriched_users = []
        for user_data in data.get("users_tienda", []):
            enriched = self._enrich_user(user_data, instance, ALL_PERMISSIONS)
            if enriched is not None:
                enriched_users.append(enriched)

        data["users_tienda"] = enriched_users

        if "propietario_data" in data:
            data["propietario_data"] = self._build_propietario_data(instance, ALL_PERMISSIONS)
        elif data.get("propietario") is not None and "propietario_data" not in data:
            data["propietario_data"] = self._build_propietario_data(instance, ALL_PERMISSIONS)

        return data
