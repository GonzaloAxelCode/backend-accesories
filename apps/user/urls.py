from django.urls import path


from .views import (
    CreateUserInTiendaAPIView,
    CustomTokenObtainPairView,
    GetAllUsersAPIView,
    GetCurrentUserAPIView,
    
    
    UpdateUserAPIView,
    DeleteUserAPIView,
    UpdateUserPermissionsView
)

urlpatterns = [
    
   path('usuarios/tienda/<int:tienda_id>/', GetAllUsersAPIView.as_view(), name='get_users_by_store'),
 
    path('usuarios/create/<int:tienda_id>/', CreateUserInTiendaAPIView.as_view(), name='create_user'),
    path('usuarios/update/<int:id>/', UpdateUserAPIView.as_view(), name='update_user'),
    path('usuarios/delete/<int:id>/', DeleteUserAPIView.as_view(), name='delete_user'),
    path('usuarios/update/permissions/<int:user_id>/', UpdateUserPermissionsView.as_view(), name='update-user-permissions'),
    path('usuarios/me/', GetCurrentUserAPIView.as_view(), name='current-user'),
    path("auth/jwt/create/custom/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),

]
