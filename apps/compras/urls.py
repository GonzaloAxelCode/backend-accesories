from django.urls import path
from .views import CrearCompraView, ListaComprasView, ActualizarCompraView

urlpatterns = [
    # Endpoints únicos y simples
    path('compras/crear/', CrearCompraView.as_view(), name='crear-compra'),
    path('compras/lista/', ListaComprasView.as_view(), name='lista-compras'),
    path('compras/actualizar/<int:id>/', ActualizarCompraView.as_view(), name='actualizar-compra'),

    # Aliases legacy (frontend antiguo) -> misma vista unificada
    path('compras/comprobante/crear/', CrearCompraView.as_view(), name='crear-comprobante-compra'),
    path('compras/comprobante/lista/', ListaComprasView.as_view(), name='lista-comprobantes-compra'),
    path('compras/comprobante/actualizar/<int:id>/', ActualizarCompraView.as_view(), name='actualizar-comprobante-compra'),
]
