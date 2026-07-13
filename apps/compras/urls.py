from django.urls import path
from .views import CrearComprobanteCompraView, ListaComprobantesCompraView

urlpatterns = [
    path('compras/comprobante/crear/', CrearComprobanteCompraView.as_view(), name='crear-comprobante-compra'),
    path('compras/comprobante/lista/', ListaComprobantesCompraView.as_view(), name='lista-comprobantes-compra'),
]
