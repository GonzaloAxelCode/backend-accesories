
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import UserAccount
from .serializers import UserAccountSerializer

class GetAllUsersAPIView(APIView):
    def get(self, request):
        users = UserAccount.objects.all()
        serializer = UserAccountSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
class GetUserAPIView(APIView):
    def get(self, request, id):
        user = get_object_or_404(UserAccount, id=id)
        serializer = UserAccountSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
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
        serializer = UserAccountSerializer(user, data=request.data, partial=True)  # partial=True para no requerir todos los campos
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
