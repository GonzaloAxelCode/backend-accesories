from django.urls import path

from apps.venta.views import CancelarVentaView, EliminarVentaView, RegistrarVentaView, VentasPorTiendaView
KEY_DEVELOPMENT_ACTIONS = "secret"
urlpatterns = [
    path('ventas/crear/', RegistrarVentaView.as_view(), name='crear_venta'),
    path('ventas/tienda/<int:tienda_id>/', VentasPorTiendaView.as_view(), name='ventas-por-tienda'),
    path('ventas/cancelar/<int:venta_id>/', CancelarVentaView.as_view(), name='cancelar-venta'),
    path(f'ventas/delete/{KEY_DEVELOPMENT_ACTIONS}/<int:venta_id>/', EliminarVentaView.as_view())
]

