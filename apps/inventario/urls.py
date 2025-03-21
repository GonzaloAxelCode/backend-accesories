from django.urls import path
from apps.inventario.views import (
    CrearInventario,
    EliminarInventario,
    ObtenerInventarioProducto,
    ObtenerInventarioTienda,
    ActualizarStock,
    ActualizarInventarioView,
    VerificarStock
)

urlpatterns = [
    path('inventarios/create/', CrearInventario.as_view(), name='create_inventari'),
    path('inventarios/producto/<int:producto_id>/', ObtenerInventarioProducto.as_view(), name='obtener_inventario_producto'),
    path('inventarios/tienda/<int:tienda_id>/', ObtenerInventarioTienda.as_view(), name='obtener_inventario_tienda'),
    path('inventarios/actualizar-stock/<int:inventario_id>/', ActualizarStock.as_view(), name='actualizar_stock'),
    path('inventarios/actualizar/<int:id>/', ActualizarInventarioView.as_view(), name='actializar_inventario'),
    path('inventarios/verificar-stock/<int:inventario_id>/', VerificarStock.as_view(), name='verificar_stock'),
    path('inventarios/eliminar/<int:inventario_id>/', EliminarInventario.as_view(), name='eliminar_stock'),
]
