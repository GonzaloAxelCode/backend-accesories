from django.urls import path
from apps.inventario.views import (
    CrearInventario,
    ObtenerInventarioProducto,
    ObtenerInventarioTienda,
    ActualizarStock,
    AjustarStock,
    VerificarStock
)

urlpatterns = [
    path('inventarios/create/', CrearInventario.as_view(), name='create_inventari'),
    path('inventarios/producto/<int:producto_id>/', ObtenerInventarioProducto.as_view(), name='obtener_inventario_producto'),
    path('inventarios/tienda/<int:tienda_id>/', ObtenerInventarioTienda.as_view(), name='obtener_inventario_tienda'),
    path('inventarios/actualizar-stock/<int:inventario_id>/', ActualizarStock.as_view(), name='actualizar_stock'),
    path('inventarios/ajustar-stock/<int:inventario_id>/', AjustarStock.as_view(), name='ajustar_stock'),
    path('inventarios/verificar-stock/<int:inventario_id>/', VerificarStock.as_view(), name='verificar_stock'),
]
