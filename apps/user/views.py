
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import UserAccount
from .serializers import CustomTokenObtainPairSerializer, UserAccountSerializer, UserSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

User = get_user_model()

class GetAllUsersAPIView(APIView):
    def get(self, request):
        # Obtener el usuario autenticado
        authenticated_user = request.user

        # Excluir al usuario autenticado de la lista de usuarios
        users = UserAccount.objects.exclude(id=authenticated_user.id)

        # Obtener todos los permisos disponibles en el sistema
        all_permissions = Permission.objects.values("codename", "name")

        # Crear un arreglo para los usuarios con sus permisos
        user_data = []
        for user in users:
            # Verificar si el usuario tiene cada permiso y devolverlo como booleano
            permissions = {
                perm["codename"]: user.has_perm(f"{perm['codename']}") for perm in all_permissions
            }

            # Agregar los datos serializados del usuario junto con los permisos
            serialized_user = UserSerializer(user).data
            serialized_user["permissions"] = permissions
            user_data.append(serialized_user)

        return Response(user_data, status=status.HTTP_200_OK)

class GetUserAPIView(APIView):
    def get(self, request, id):
        # Obtener el usuario por su ID
        user = get_object_or_404(UserAccount, id=id)

        # Serializar los datos del usuario
        serializer = UserAccountSerializer(user)

        # Obtener todos los permisos disponibles en el sistema
        all_permissions = Permission.objects.values("codename", "name")

        # Crear un diccionario de permisos con valores booleanos
        permissions = {
            perm["codename"]: user.has_perm(f"{perm['codename']}") for perm in all_permissions
        }

        # Respuesta con los datos del usuario y sus permisos
        return Response({
            "user": {
                **serializer.data,  # Serializar datos básicos del usuario
                "permissions": permissions  # Incluir permisos como booleanos
            }
        }, status=status.HTTP_200_OK)
        
class CreateUserAPIView(APIView):
    def post(self, request):
        serializer = UserAccountSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Usuario creado exitosamente",
                "user": serializer.data
            }, status=status.HTTP_201_CREATED)
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