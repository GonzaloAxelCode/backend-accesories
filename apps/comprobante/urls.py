from apps.comprobante.views import ConsultaDocumentoView, RegistrarNotaCreditoView, ValidarCompraView, GuardarCompraView
from django.urls import path

urlpatterns = [
    path('consulta-documento/', ConsultaDocumentoView.as_view(), name='consulta-docs'),
    path('nota-credito/registrar/', RegistrarNotaCreditoView.as_view(), name='nota-credito-registrar'),
    path('compra/validar/', ValidarCompraView.as_view(), name='compra-validar'),
    path('compra/guardar/', GuardarCompraView.as_view(), name='compra-guardar'),
]