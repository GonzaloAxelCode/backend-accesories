from django.urls import path

from apps.pedidos.views import CrearPedidoView, ListaPedidosView, BuscarPedidoView, CancelarPedidoView

urlpatterns = [
    path('pedidos/crear/', CrearPedidoView.as_view(), name='crear-pedido'),
    path('pedidos/lista/', ListaPedidosView.as_view(), name='lista-pedidos'),
    path('pedidos/buscar/', BuscarPedidoView.as_view(), name='buscar-pedidos'),
    path('pedidos/cancelar/<int:pedido_id>/', CancelarPedidoView.as_view(), name='cancelar-pedido'),
]
