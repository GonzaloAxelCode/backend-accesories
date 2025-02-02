from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from django.contrib.auth import get_user_model

from apps.user.models import UserAccount
User = get_user_model()


class UserAcountCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User

        fields = '__all__'



class UserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'username', 'first_name', 'last_name', 'password', 'photo_url', 'is_active']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = UserAccount.objects.create_user( # type: ignore
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            photo_url=validated_data.get('photo_url', "https://res.cloudinary.com/ddksrkond/image/upload/v1688411778/default_dfvymc.webp"),
            is_active=validated_data.get('is_active', True)
        )
        return user