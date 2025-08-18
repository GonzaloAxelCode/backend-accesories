
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from core.permissions import IsSuperUser
from .models import UserAccount
from .serializers import CustomTokenObtainPairSerializer, UserAccountSerializer, UserSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
        
User = get_user_model()

class GetAllUsersAPIView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        authenticated_user = request.user
        
        users = UserAccount.objects.exclude(id=authenticated_user.id).filter(is_superuser=False)


        # 1. Obtener TODOS los permisos definidos en Meta (array de strings)
        all_permissions_meta = [perm[0] for perm in UserAccount._meta.permissions]

        users_data = []
        for user in users:
            # 2. Obtener los permisos del usuario actual (solo los que están en Meta)
            user_permissions_raw = user.get_all_permissions()  # Permisos en formato 'app_label.perm_codename'
            
            # Filtramos para quedarnos solo con los permisos definidos en Meta
            user_permissions_filtered = [
                perm.split('.')[1]  # Extraemos solo el 'perm_codename' (ej: 'can_make_sale')
                for perm in user_permissions_raw
                if perm.split('.')[1] in all_permissions_meta  # Solo si está en Meta
            ]
            all_permissions_meta = [perm[0] for perm in UserAccount._meta.permissions]

            # 3. Construir el diccionario de permisos {permiso: bool}
            permissions = {}
            for perm in all_permissions_meta:
                permissions[perm] = perm in user_permissions_filtered  # True si lo tiene, False si no


            # 4. Construir el JSON del usuario
            user_data = {
                'id': user.id, # type: ignore
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
                'permissions': permissions,  # Diccionario de permisos (Meta + bool)
                'user_permissions_list': user_permissions_filtered,  # Solo permisos de Meta que tiene el usuario
                "all_permissions_meta":all_permissions_meta
            }
            users_data.append(user_data)

        return Response(users_data)


class GetUserAPIView(APIView):
    def get(self, request, id):
        # Obtener el usuario por su ID
        user = get_object_or_404(UserAccount, id=id)

        # 1. Obtener TODOS los permisos definidos en Meta (array de strings)
        all_permissions_meta = [perm[0] for perm in UserAccount._meta.permissions]

        # 2. Obtener los permisos del usuario actual (solo los que están en Meta)
        user_permissions_raw = user.get_all_permissions()  # Permisos en formato 'app_label.perm_codename'
        
        # Filtrar para quedarnos solo con los permisos definidos en Meta
        user_permissions_filtered = [
            perm.split('.')[1]  # Extraemos solo el 'perm_codename' (ej: 'can_make_sale')
            for perm in user_permissions_raw
            if perm.split('.')[1] in all_permissions_meta  # Solo si está en Meta
        ]

        # 3. Construir el diccionario de permisos {permiso: bool}
        permissions_dict = {
            perm: perm in user_permissions_filtered 
            for perm in all_permissions_meta
        }

        # 4. Construir la respuesta
        response_data = {
            'id': user.id, # type: ignore
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
            'permissions': permissions_dict,  # Diccionario de permisos (Meta + bool)
            'user_permissions_list': user_permissions_filtered,  # Solo permisos de Meta que tiene el usuario
            'all_permissions_meta': all_permissions_meta  # Todos los permisos posibles (Meta)
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
    
    
class CreateUserInTiendaAPIView(APIView):
    def post(self, request):
        # Verificar si el usuario tiene permiso
        if not request.user.has_perm("apps.user.can_create_user"):
            return Response({"error": "No tiene permiso para crear usuarios"}, status=status.HTTP_403_FORBIDDEN)
        
        # Clonar los datos enviados y forzar la tienda del usuario logueado
        data = request.data.copy()
        data["tienda"] = request.user.tienda.id  # <- fuerza la tienda propia

        serializer = UserAccountSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Usuario creado exitosamente", "usuario": serializer.data}, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class UpdateUserAPIView(APIView):
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
    def delete(self, request, id):
        user = get_object_or_404(UserAccount, id=id)
        user.delete()
        return Response({
            "message": "Usuario eliminado exitosamente"
        }, status=status.HTTP_204_NO_CONTENT)

class UserPermissionsView(APIView):

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
    """
    Vista para que un superusuario asigne o elimine permisos de un usuario.
    """

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