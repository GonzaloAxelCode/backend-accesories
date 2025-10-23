from django.urls import path
from .views import CreateTienda, DeleteTienda, GetAllTiendas, GetTienda, UpdateTienda, DeactivateTienda

urlpatterns = [
    path('tiendas/', GetAllTiendas.as_view(), name='get_all_tiendas'),
    path('tiendas/create/', CreateTienda.as_view(), name='create_tienda'),
    path('tiendas/<int:id>/', GetTienda.as_view(), name='get_tienda'),
    path('tiendas/update/<int:id>/', UpdateTienda.as_view(), name='update_tienda'),
    path('tiendas/desactivate/<int:id>/', DeactivateTienda.as_view(), name='deactivate_tienda'),
    path('tiendas/delete/<int:id>/', DeleteTienda.as_view(), name='delete_tienda'),
]
