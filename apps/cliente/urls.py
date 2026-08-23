from django.urls import path

from apps.cliente.views import CreateCliente, DeactivateCliente, GetAllClientes, GetCliente, ResumenClientesView

urlpatterns = [
    path('clientes/', GetAllClientes.as_view(), name='get_all_clientes'),
    path('clientes/create/', CreateCliente.as_view(), name='create_cliente'),
    path('clientes/resumen/', ResumenClientesView.as_view(), name='resumen-clientes'),
    path('clientes/deactivate/<str:document>/', DeactivateCliente.as_view(), name='deactivate_cliente'),
    path('clientes/<str:document>/', GetCliente.as_view(), name='get_cliente'),
]
