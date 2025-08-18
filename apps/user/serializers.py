from djoser.serializers import UserCreateSerializer
from requests import Response
from rest_framework import serializers

from django.contrib.auth import get_user_model


from rest_framework_simplejwt.views import TokenObtainPairView

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.views import APIView

from rest_framework import status

from apps.user.models import UserAccount
User = get_user_model()
from django.contrib.auth.models import Permission


class UserAcountCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = '__all__'


class UserAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        
        fields = '__all__'
        
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

    def to_representation(self, instance):
        # Serializar los datos normales del usuario
        data = super().to_representation(instance)

        # Obtener el app_label del modelo
        app_label = 'apps.user'
        
        # Filtrar permisos relevantes del modelo UserAccount
        relevant_permissions = Permission.objects.filter(content_type__app_label=app_label)
        
        # Construir un diccionario con los permisos y si el usuario los tiene
        permissions = {
            perm.codename: instance.has_perm(f"{app_label}.{perm.codename}") for perm in relevant_permissions
        }
        
        # Agregar los permisos al resultado serializado
        data['permissions'] = permissions
        return data

class UserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        # Extraer tienda_id si viene del frontend
        tienda = validated_data.pop('tienda', None)

        # Crear el usuario
        user = UserAccount.objects.create_user(  # type: ignore
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            photo_url=validated_data.get(
                'photo_url',
                "https://res.cloudinary.com/ddksrkond/image/upload/v1688411778/default_dfvymc.webp"
            ),
            is_active=validated_data.get('is_active', True),
            tienda=tienda  # asignar la tienda directamente
        )
        return user
    
    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user_id"] = self.user.id  # type: ignore # Agrega el ID del usuario
        data["tienda_id"] = self.user.tienda.id  # type: ignore # <- Agrega la tienda asociada
        data["is_superuser"] = self.user.is_superuser # type: ignore
        data["es_empleado"] = self.user.es_empleado # type: ignore

        print(data)  
        return data
class UpdatePasswordAPIView(APIView):
    def put(self, request, user_id):
        try:
            # Obtener el usuario por ID
            user = User.objects.get(id=user_id)
            
            # Obtener la nueva contraseña desde el cuerpo del request
            new_password = request.data.get("new_password")

            if not new_password:
                return Response({"error": "La nueva contraseña es requerida"}, status=status.HTTP_400_BAD_REQUEST) # type: ignore

            # Establecer la nueva contraseña (hash automáticamente)
            user.set_password(new_password)
            user.save()

            return Response({"message": "Contraseña actualizada exitosamente"}, status=status.HTTP_200_OK) # type: ignore

        except User.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND) # type: ignore