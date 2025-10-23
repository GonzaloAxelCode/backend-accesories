# apps/tienda/serializers.py
from rest_framework import serializers

from apps.user.models import UserAccount
from apps.user.serializers import UserSerializer
from .models import Tienda


class TiendaSerializer(serializers.ModelSerializer):
    encargado = UserSerializer(read_only=True)   # OneToOne
    users_tienda = UserSerializer(many=True, read_only=True)  # FK reverse relation

    class Meta:
        model = Tienda
        fields = '__all__'

    def to_representation(self, instance):
        # Obtenemos la representación base
        data = super().to_representation(instance)

        # 🔹 Definir lista de permisos base
        ALL_PERMISSIONS = [
            "can_make_sale",
            "can_cancel_sale",
            "can_create_inventory",
            "can_modify_inventory",
            "can_update_inventory",
            "can_delete_inventory",
            "can_create_product",
            "can_update_product",
            "can_delete_product",
            "can_create_category",
            "can_modify_category",
            "can_delete_category",
            "can_create_supplier",
            "can_modify_supplier",
            "can_delete_supplier",
            "can_create_store",
            "can_modify_store",
            "can_delete_store",
            "view_sale",
            "view_inventory",
            "view_product",
            "view_category",
            "view_supplier",
            "view_store",
            "can_create_user",
            "can_create_proveedor",
            "can_update_proveedor",
            "can_delete_proveedor",
        ]

        # 🔹 Enriquecer los usuarios de la tienda con sus permisos
        enriched_users = []
        for user_data in data.get("users_tienda", []):
            try:
                user_obj = UserAccount.objects.get(id=user_data["id"])

                # Obtener permisos reales del usuario
                user_permissions_full = user_obj.get_all_permissions()
                user_permission_codenames = [
                    perm.split('.')[1] for perm in user_permissions_full
                ]

                permissions_dict = {
                    perm: perm in user_permission_codenames for perm in ALL_PERMISSIONS
                }

                # Añadir permisos al diccionario del usuario
                user_data["permissions"] = permissions_dict
                user_data["user_permissions_list"] = user_permission_codenames
                user_data["all_permissions_meta"] = ALL_PERMISSIONS
                user_data["tienda_nombre"] = instance.nombre

                enriched_users.append(user_data)
            except UserAccount.DoesNotExist:
                continue

        data["users_tienda"] = enriched_users
        return data
