from django.urls import path

from apps.pedidos.views import (
    CrearPedidoView,
    ListarPedidosView,
    ActualizarPedidoView,
    CancelarPedidoView,
    DetallePedidoView,
    ConfirmarEstadoPedidoView,
    EliminarPedidoView,
)

urlpatterns = [
    path('pedidos/crear/', CrearPedidoView.as_view(), name='crear-pedido'),
    path('pedidos/lista/', ListarPedidosView.as_view(), name='lista-pedidos'),
    path('pedidos/<int:pedido_id>/', DetallePedidoView.as_view(), name='detalle-pedido'),
    path('pedidos/<int:pedido_id>/actualizar/', ActualizarPedidoView.as_view(), name='actualizar-pedido'),
    path('pedidos/<int:pedido_id>/estado/', ConfirmarEstadoPedidoView.as_view(), name='confirmar-estado-pedido'),
    path('pedidos/<int:pedido_id>/cancelar/', CancelarPedidoView.as_view(), name='cancelar-pedido'),
    path('pedidos/<int:pedido_id>/eliminar/', EliminarPedidoView.as_view(), name='eliminar-pedido'),
]
