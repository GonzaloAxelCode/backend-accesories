from django.urls import path
from .views import DetalleCompraView, EliminarCompraView, GuardarCompraView, ListaComprasView, ActualizarArchivosCompraView

urlpatterns = [
    path('compras/guardar/', GuardarCompraView.as_view(), name='guardar-compra'),
    path('compras/lista/', ListaComprasView.as_view(), name='lista-compras'),
    path('compras/<int:id>/', DetalleCompraView.as_view(), name='detalle-compra'),
    path('compras/<int:id>/archivos/', ActualizarArchivosCompraView.as_view(), name='actualizar-archivos-compra'),
    path('compras/eliminar/<int:id>/', EliminarCompraView.as_view(), name='eliminar-compra'),
]
