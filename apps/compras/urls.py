from django.urls import path
from .views import CrearComprobanteCompraView, ListaComprobantesCompraView, SubirComprobanteCompraFilesView, ListarComprobanteCompraFilesView

urlpatterns = [
    path('compras/comprobante/crear/', CrearComprobanteCompraView.as_view(), name='crear-comprobante-compra'),
    path('compras/comprobante/lista/', ListaComprobantesCompraView.as_view(), name='lista-comprobantes-compra'),
    path('compras/comprobante/subir-files/', SubirComprobanteCompraFilesView.as_view(), name='subir-comprobante-files'),
    path('compras/comprobante/files/', ListarComprobanteCompraFilesView.as_view(), name='lista-comprobante-files'),
]
