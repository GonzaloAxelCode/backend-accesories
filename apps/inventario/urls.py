from django.urls import path
from apps.inventario.views import (
    BuscarInventarioAPIView,
    CrearInventario,
    DistribucionStockView,
    EliminarInventario,
    GetAllInventarioAPIView,
    ObtenerInventarioProducto,
    PorcentajeProductosPorCategoriaView,
    ProductosPorRangoPreciosView,
    TopCategoriasPorCompraView,
    ValorizacionInventarioView,
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
    path('productos-menor-stock/', ProductosConMenorStockView.as_view(), name='productos-menor-stock'),
    path('buscar-inventario/', BuscarInventarioAPIView.as_view(), name='buscar-inventario'),
    path('inventarios/porcentaje-por-categoria/', PorcentajeProductosPorCategoriaView.as_view(), name='porcentaje-por-categoria'),
    path('inventarios/distribucion-stock/', DistribucionStockView.as_view(), name='distribucion-stock'),
    path('inventarios/por-rango-precios/', ProductosPorRangoPreciosView.as_view(), name='por-rango-precios'),
    path('inventarios/valorizacion/', ValorizacionInventarioView.as_view(), name='valorizacion-inventario'),
    path('inventarios/top-categorias-compra/', TopCategoriasPorCompraView.as_view(), name='top-categorias-compra'),

]
