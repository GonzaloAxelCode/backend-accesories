from django.urls import path
from apps.inventario.views import (
    BuscarInventarioAPIView,
    CrearInventario,
    EliminarInventario,
    GetAllInventarioAPIView,
    ObtenerInventarioProducto,
    
    ActualizarStock,
    ActualizarInventarioView,
    ProductosConMenorStockView,
    VerificarStock
)

urlpatterns = [
    path('inventarios/', GetAllInventarioAPIView.as_view(), name='obtener_inventario_tienda'),
    path('inventarios/create/', CrearInventario.as_view(), name='create_inventari'),
    path('inventarios/producto/<int:producto_id>/', ObtenerInventarioProducto.as_view(), name='obtener_inventario_producto'),
    path('inventarios/actualizar-stock/<int:inventario_id>/', ActualizarStock.as_view(), name='actualizar_stock'),
    path('inventarios/actualizar/<int:id>/', ActualizarInventarioView.as_view(), name='actializar_inventario'),
    path('inventarios/verificar-stock/<int:inventario_id>/', VerificarStock.as_view(), name='verificar_stock'),
    path('inventarios/eliminar/<int:inventario_id>/', EliminarInventario.as_view(), name='eliminar_stock'),
    path('productos-menor-stock/<int:tienda_id>/', ProductosConMenorStockView.as_view(), name='productos-menor-stock'),
    path('buscar-inventario/', BuscarInventarioAPIView.as_view(), name='buscar-inventario'),

]
