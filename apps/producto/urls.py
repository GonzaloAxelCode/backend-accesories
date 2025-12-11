from django.urls import path
from .views import (
    BuscarProductoAPIView,
    CreateProductoAPIView,
    GetAllProductosAPIView,
    GetAllProductosAPIViewWithPagination,
    
    GetProductoAPIView,
    UpdateProductoAPIView,
    DeleteProductoAPIView
)

urlpatterns = [
    path('productos/', GetAllProductosAPIViewWithPagination.as_view(), name='get_all_productos'),
    path('productos/<int:id>/', GetProductoAPIView.as_view(), name='get_producto'),
    path('productos/create/', CreateProductoAPIView.as_view(), name='create_producto'),
    path('productos/update/<int:id>/', UpdateProductoAPIView.as_view(), name='update_producto'),
    path('productos/delete/<int:id>/',DeleteProductoAPIView.as_view(),name='delete_producto'),
    path('productos/buscar-producto/', BuscarProductoAPIView.as_view(), name='buscar_producto'),

]
