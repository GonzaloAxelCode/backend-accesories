from django.urls import path

from apps.venta.views import CancelarVentaView, EliminarVentaView, ProductosMasVendidosView, RegistrarVentaAnonimaView, RegistrarVentaSinComprobanteView, RegistrarVentaView, VentaBusquedaView, VentaSalesByDateView, VentasPerDayOrMonth, VentasPorTiendaView, VentasResumenView
KEY_DEVELOPMENT_ACTIONS = "secret"
urlpatterns = [
    path('ventas/crear/', RegistrarVentaView.as_view(), name='crear_venta'),
    path('ventas/crear/pendiente/', RegistrarVentaSinComprobanteView.as_view(), name='crear_venta_sin_comprobante'),
    path('ventas/crear/anonima/', RegistrarVentaAnonimaView.as_view(), name='anonimo'),
    path('ventas/tienda/', VentasPorTiendaView.as_view(), name='ventas-por-tienda'),
    path('ventas/cancelar/<int:venta_id>/', CancelarVentaView.as_view(), name='cancelar-venta'),
    path(f'ventas/delete/{KEY_DEVELOPMENT_ACTIONS}/<int:venta_id>/', EliminarVentaView.as_view()),
    path('ventas/resumen/', VentasResumenView.as_view(), name='ventas-resumen'),
    path('sales-by-date/', VentaSalesByDateView.as_view(), name='venta-sales-by-date'),
    path('top-productos-vendidos/', ProductosMasVendidosView.as_view(), name='top-productos-vendidos'),
    path('ventas/resumenbymonthorday/', VentasPerDayOrMonth.as_view(), name='ventas-resumen-bymonthorday'),
    path("ventas/search/",VentaBusquedaView.as_view(),name="Venta Busqueda")
]

