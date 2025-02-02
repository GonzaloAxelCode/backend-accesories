from django.urls import path

from apps.proveedor.views import CreateProveedor, DeactivateProveedor, GetAllProveedores, GetProveedor, UpdateProveedor

urlpatterns = [

    path('proveedores/', GetAllProveedores.as_view(), name='get_all_proveedores'),
    path('proveedores/create/', CreateProveedor.as_view(), name='create_proveedor'),
    path('proveedores/<int:id>/', GetProveedor.as_view(), name='get_proveedor'),
    path('proveedores/update/<int:id>/', UpdateProveedor.as_view(), name='update_proveedor'),
    path('proveedores/deactivate/<int:id>/', DeactivateProveedor.as_view(), name='deactivate_proveedor'),
]
