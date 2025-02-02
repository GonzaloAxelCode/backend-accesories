from django.urls import path
from .views import (
    CreateUserAPIView,
    GetAllUsersAPIView,
    GetUserAPIView,
    
    UpdateUserAPIView,
    DeleteUserAPIView
)

urlpatterns = [
    path('usuarios/', GetAllUsersAPIView.as_view(), name='get_all_users'),
    path('usuarios/<int:id>/', GetUserAPIView.as_view(), name='get_user'),
    path('usuarios/create/', CreateUserAPIView.as_view(), name='create_user'),
    path('usuarios/update/<int:id>/', UpdateUserAPIView.as_view(), name='update_user'),
    path('usuarios/delete/<int:id>/', DeleteUserAPIView.as_view(), name='delete_user'),
]
