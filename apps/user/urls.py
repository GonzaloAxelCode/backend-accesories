from django.urls import path


from .views import (
    CreateUserInTiendaAPIView,
    CustomTokenObtainPairView,
    GetAllUsersAPIView,
    GetCurrentUserAPIView,
    UpdateUserAPIView,
    
    UpdateUserPermissionsView,
    ToggleUserDeletedAPIView,
    UserConfigUpdateAPIView,
    UpdateUserBasicDataAPIView,
    AdminResetPasswordAPIView,
)

urlpatterns = [
    
   path('usuarios/tienda/<int:tienda_id>/', GetAllUsersAPIView.as_view(), name='get_users_by_store'),
 
    path('usuarios/create/<int:tienda_id>/', CreateUserInTiendaAPIView.as_view(), name='create_user'),
    path('usuarios/update/<int:id>/', UpdateUserAPIView.as_view(), name='update_user'),
    
    path('usuarios/toggle-deleted/<int:id>/', ToggleUserDeletedAPIView.as_view(), name='toggle_user_deleted'),
    path('usuarios/update/permissions/<int:user_id>/', UpdateUserPermissionsView.as_view(), name='update-user-permissions'),
    path('usuarios/me/', GetCurrentUserAPIView.as_view(), name='current-user'),
    path('usuarios/config/', UserConfigUpdateAPIView.as_view(), name='update-user-config'),
    path('usuarios/update/basic/<int:id>/', UpdateUserBasicDataAPIView.as_view(), name='update_user_basic'),
    path('usuarios/admin/reset-password/<int:id>/', AdminResetPasswordAPIView.as_view(), name='admin_reset_password'),
    path("auth/jwt/create/custom/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),

]
