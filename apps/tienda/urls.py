from django.urls import path
from .views import CreateTienda, GetAllTiendas, GetTienda, UpdateTienda, DeactivateTienda

urlpatterns = [
    path('tiendas/', GetAllTiendas.as_view(), name='get_all_tiendas'),
    path('tiendas/create/', CreateTienda.as_view(), name='create_tienda'),
    path('tiendas/<int:id>/', GetTienda.as_view(), name='get_tienda'),
    path('tiendas/update/<int:id>/', UpdateTienda.as_view(), name='update_tienda'),
    path('tiendas/deactivate/<int:id>/', DeactivateTienda.as_view(), name='deactivate_tienda'),
]
