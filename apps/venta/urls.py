from django.urls import path

from apps.venta.views import CrearVenta, VentasPorTienda




urlpatterns = [
    path('ventas/crear/', CrearVenta.as_view(), name='crear_venta'),
    path('ventas/tienda/<int:tienda_id>/', VentasPorTienda.as_view(), name='ventas_por_tienda'),
]

