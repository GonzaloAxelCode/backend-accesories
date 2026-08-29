from django.urls import path
from .views import (
    CreateTienda, GetAllTiendas, GetTienda, UpdateTienda,
    DeactivateTienda, HabilitarTiendaEliminada, GetMiTiendaView
)

urlpatterns = [
    # Tiendas (superuser)
    path('tiendas/', GetAllTiendas.as_view(), name='get_all_tiendas'),
    path('tiendas/create/', CreateTienda.as_view(), name='create_tienda'),

    # Ver/actualizar tienda
    path('tiendas/<int:id>/', GetTienda.as_view(), name='get_tienda'),
    path('tiendas/update/<int:id>/', UpdateTienda.as_view(), name='update_tienda'),
    path('tiendas/desactivate/<int:id>/', DeactivateTienda.as_view(), name='deactivate_tienda'),
    path('tiendas/habilitar/<int:id>/', HabilitarTiendaEliminada.as_view(), name='habilitar_tienda'),

    # Mi tienda
    path('mi-tienda/', GetMiTiendaView.as_view(), name='get_mi_tienda'),
]
