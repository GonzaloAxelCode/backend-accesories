from django.urls import path
from .views import (
    BuscarProductoAPIView,
    BuscarProductoPorSKUAPIView,
    CreateProductoAPIView,
    GetAllProductosAPIView,
    GetAllProductosAPIViewWithPagination,
   CreateProductoAPIViewReactNative ,
    GetProductoAPIView,
    UpdateProductoAPIView,
    DeleteProductoAPIView ,
    UpdateProductoAPIViewReactNative
)

urlpatterns = [
    path('productos/', GetAllProductosAPIViewWithPagination.as_view(), name='get_all_productos'),
    path('productos/<int:id>/', GetProductoAPIView.as_view(), name='get_producto'),
    path('productos/update/<int:id>/', UpdateProductoAPIView.as_view(), name='update_producto'),
    path('productos/create/', CreateProductoAPIView.as_view(), name='create_producto'),
    path('productos/create_with_base64/', CreateProductoAPIViewReactNative.as_view(), name='create_producto_react_native'),
    path('productos/update_with_base64/<int:id>/', UpdateProductoAPIViewReactNative.as_view(), name='update_producto_react_native'),
    path('productos/delete/<int:id>/',DeleteProductoAPIView.as_view(),name='delete_producto'),
    path('productos/buscar-producto/', BuscarProductoAPIView.as_view(), name='buscar_producto'),
    path('productos/buscar-por-sku/', BuscarProductoPorSKUAPIView.as_view(), name='buscar_producto_por_sku'),

]
