
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.tienda.models import Tienda
from apps.tienda.serializers import TiendaSerializer
from core.permissions import IsSuperUser
from .models import UserAccount
from .serializers import CustomTokenObtainPairSerializer, UserAccountSerializer, UserSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from rest_framework.permissions import IsAuthenticated        
User = get_user_model()
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404


from rest_framework import status

class GetAllUsersAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request, tienda_id=None):
        authenticated_user = request.user

        # 🔹 Validar si existe la tienda
        if not Tienda.objects.filter(id=tienda_id).exists():
            return Response(
                {"detail": f"No existe la tienda con id {tienda_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 🔹 Excluir usuario autenticado y superusuarios
        users = (
            UserAccount.objects.exclude(id=authenticated_user.id)
            .filter(is_superuser=False, tienda_id=tienda_id)
        )
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

        all_system_permissions = Permission.objects.filter(codename__in=ALL_PERMISSIONS)

        users_data = []

        for user in users:
            user_permissions = user.user_permissions.all() | Permission.objects.filter(group__user=user)
            user_permission_codenames = set(user_permissions.values_list("codename", flat=True))

            permissions_dict = {
                perm.codename: perm.codename in user_permission_codenames
                for perm in all_system_permissions
            }

            user_data = {
                "id": user.id, # type: ignore
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "photo_url": user.photo_url,
                "date_joined": user.date_joined,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "es_empleado": user.es_empleado,
                "desactivate_account": user.desactivate_account,
                "permissions": permissions_dict,
                "user_permissions_list": list(user_permission_codenames),
                "all_permissions_meta": ALL_PERMISSIONS,
                "tienda": user.tienda.id if user.tienda else None, # type: ignore
                "tienda_nombre": user.tienda.nombre if user.tienda else None,
                
            }

            users_data.append(user_data)

        return Response(users_data, status=status.HTTP_200_OK)





class GetCurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(UserAccount, id=request.user.id)

        # 🔹 1. Definir permisos manualmente (solo codenames)
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

        # 🔹 2. Obtener todos los permisos del usuario
        user_permissions_full = user.get_all_permissions()

        # 🔹 3. Extraer solo los codenames (ejemplo: 'can_make_sale')
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]

        # 🔹 4. Crear el diccionario con True / False
        permissions_dict = {
            perm: perm in user_permission_codenames for perm in ALL_PERMISSIONS
        }
        tienda_data = (
            TiendaSerializer(
                user.tienda,
                context={"request": request}  # útil para URLs absolutas
            ).data
            if user.tienda else None
        )

        # 🔹 5. Construir la respuesta
        response_data = {
            'id': user.id,  # type: ignore
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'photo_url': user.photo_url,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'es_empleado': user.es_empleado,
            'desactivate_account': user.desactivate_account,
            'permissions': permissions_dict,
            'user_permissions_list': user_permission_codenames,
            'all_permissions_meta': ALL_PERMISSIONS,
            'tienda': user.tienda.id if user.tienda else None,  # type: ignore
            'tienda_nombre': user.tienda.nombre if user.tienda else None,
            'tienda_data': tienda_data,

        }

        return Response(response_data, status=status.HTTP_200_OK)
    
class CreateUserInTiendaAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, tienda_id):
        tienda = get_object_or_404(Tienda, id=tienda_id)

        # Clonar los datos y forzar la tienda
        data = request.data.copy()
        data["tienda"] = tienda.id  # type: ignore

        serializer = UserAccountSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Guardar el nuevo usuario
        user = serializer.save()
        if isinstance(user, list):  # ✅ En caso de que devuelva lista
            user = user[0]

        # 🔹 Definir los permisos (igual que en GetCurrentUserAPIView)
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

        # 🔹 Obtener los permisos reales del nuevo usuario
        user_permissions_full = user.get_all_permissions()  # type: ignore
        user_permission_codenames = [
            perm.split('.')[1] for perm in user_permissions_full
        ]

        permissions_dict = {
            perm: perm in user_permission_codenames for perm in ALL_PERMISSIONS
        }

        # 🔹 Armar la respuesta igual que en GetCurrentUserAPIView
        response_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'photo_url': user.photo_url,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'es_empleado': user.es_empleado,
            'desactivate_account': user.desactivate_account,
            'permissions': permissions_dict,
            'user_permissions_list': user_permission_codenames,
            'all_permissions_meta': ALL_PERMISSIONS,
            'tienda': user.tienda.id if user.tienda else None,
            'tienda_nombre': user.tienda.nombre if user.tienda else None,
        }

        return Response(
            {"message": "Usuario creado exitosamente", "usuario": response_data},
            status=status.HTTP_201_CREATED,
        )
    
class UpdateUserAPIView(APIView):
    permission_classes = [IsAuthenticated,IsSuperUser]
    def put(self, request, id):
        user = get_object_or_404(UserAccount, id=id)
        serializer = UserAccountSerializer(user, data=request.data, partial=True) 
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Usuario actualizado exitosamente",
                "user": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class UpdateUserPermissionsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def put(self, request, user_id):
        try:
            # 🔹 Obtener el usuario
            user = UserAccount.objects.get(id=user_id)
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 🔹 Extraer el permiso individual
        perm_codename = request.data.get("permiso")
        valor = request.data.get("valor")

        if not perm_codename or valor is None:
            return Response(
                {"error": "Debes enviar 'permiso' y 'valor' (true/false)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔹 Actualizar solo ese permiso dentro de una transacción
        with transaction.atomic():
            try:
                permiso = Permission.objects.get(codename=perm_codename)
            except Permission.DoesNotExist:
                return Response(
                    {"error": f"Permiso '{perm_codename}' no encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if valor is True or valor == "true":
                user.user_permissions.add(permiso)
            elif valor is False or valor == "false":
                user.user_permissions.remove(permiso)
            else:
                return Response(
                    {"error": "'valor' debe ser true o false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 🔹 Confirmar permisos actualizados
        updated_permissions = list(user.user_permissions.values_list("codename", flat=True))

        return Response(
            {
                "message": f"Permiso '{perm_codename}' actualizado correctamente.",
                "updated_permissions": updated_permissions,
            },
            status=status.HTTP_200_OK,
        )
        
        
class UpdateUserPermissionsViewLOTE(APIView):
    permission_classes = [IsAuthenticated,IsSuperUser]
    def put(self, request, user_id):
        try:
            # Obtener el usuario
            
            print("******** antes ")
            user = UserAccount.objects.get(id=user_id)
            print(user.user_permissions.values_list("codename", flat=True))
            print("******** despues ")
        except UserAccount.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        
        # Extraer los permisos enviados en el request
        permissions_data = request.data.get("permissions", {})
        if not isinstance(permissions_data, dict):
            return Response({"error": "La propiedad 'permissions' debe ser un diccionario."}, status=status.HTTP_400_BAD_REQUEST)
        

        # Validar permisos y actualizar en una transacción
        with transaction.atomic():
            for perm_codename, value in permissions_data.items():
                try:
                    # Buscar el permiso por su `codename`
                    permission = Permission.objects.get(codename=perm_codename)
                    if value:  # Si el valor es True, agregar el permiso al usuario
                        user.user_permissions.add(permission)
                    else:  # Si el valor es False, remover el permiso del usuario
                        user.user_permissions.remove(permission)
                except Permission.DoesNotExist:
                    return Response({"error": f"Permiso '{perm_codename}' no encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        # Confirmar permisos actualizados
        updated_permissions = user.user_permissions.values_list("codename", flat=True)
        user.save()
        print(user.user_permissions.values_list("codename", flat=True))
        return Response({
            "message": "Permisos actualizados correctamente.",
            "updated_permissions": list(updated_permissions),
        }, status=status.HTTP_200_OK)

class DeleteUserAPIView(APIView):
    permission_classes = [IsAuthenticated,IsSuperUser]
    def delete(self, request, id):
        user = get_object_or_404(UserAccount, id=id)
        user.delete()
        return Response({
            "message": "Usuario eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)

class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated,IsSuperUser]
    def get(self, request):
        user = request.user
        all_permissions = dict(
            (perm[0], user.has_perm(f"app.{perm[0]}")) for perm in UserAccount._meta.permissions
        )
        return Response({
            "username": user.username,
            "permissions": all_permissions
        })
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        user_id = serializer.user.id  # Obtiene el ID del usuario
        return Response({
            "refresh": tokens["refresh"],
            "access": tokens["access"],
            "user_id": user_id
        })

class UpdatePermissionsAPIView(APIView):

    permission_classes = [IsAuthenticated,IsSuperUser]
    def patch(self, request, user_id):
        try:
            # Verifica que el usuario sea superusuario
            if not request.user.is_superuser:
                return Response(
                    {"error": "No tienes permisos para realizar esta acción."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Obtiene el usuario al que se le asignarán los permisos
            user = User.objects.get(id=user_id)

            # Datos enviados en el cuerpo de la solicitud
            permissions_data = request.data  # Ejemplo: {"can_make_sale": true, "can_delete_inventory": false}

            if not isinstance(permissions_data, dict):
                return Response(
                    {"error": "Los datos enviados deben ser un diccionario."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Procesa cada permiso enviado
            for codename, has_permission in permissions_data.items():
                if not isinstance(has_permission, bool):
                    return Response(
                        {"error": f"El valor de '{codename}' debe ser un booleano."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Busca el permiso en el sistema
                try:
                    perm = Permission.objects.get(codename=codename)
                except Permission.DoesNotExist:
                    return Response(
                        {"error": f"El permiso '{codename}' no existe."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Asigna o elimina el permiso
                if has_permission:
                    user.user_permissions.add(perm)
                else:
                    user.user_permissions.remove(perm)

            return Response(
                {"message": "Permisos actualizados exitosamente."},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )