from django.urls import path

from apps.cliente.views import CreateCliente, DeactivateCliente, GetAllClientes, GetCliente, UpdateCliente

urlpatterns = [
    path('clientes/', GetAllClientes.as_view(), name='get_all_clientes'),
    path('clientes/create/', CreateCliente.as_view(), name='create_cliente'),
    path('clientes/<str:dni>/', GetCliente.as_view(), name='get_cliente'),
    path('clientes/update/<str:dni>/', UpdateCliente.as_view(), name='update_cliente'),
    path('clientes/deactivate/<str:dni>/', DeactivateCliente.as_view(), name='deactivate_cliente'),
]
