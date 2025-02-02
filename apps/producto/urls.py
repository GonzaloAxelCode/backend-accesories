from django.urls import path
from .views import (
    CreateProductoAPIView,
    GetAllProductosAPIView,
    GetProductoAPIView,
    UpdateProductoAPIView,
    DeleteProductoAPIView
)

urlpatterns = [
    path('productos/', GetAllProductosAPIView.as_view(), name='get_all_productos'),
    path('productos/<int:id>/', GetProductoAPIView.as_view(), name='get_producto'),
    path('productos/create/', CreateProductoAPIView.as_view(), name='create_producto'),
    path('productos/update/<int:id>/', UpdateProductoAPIView.as_view(), name='update_producto'),
    
]
