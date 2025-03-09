from apps.comprobante.views import ConsultaDNIView, ConsultaDocumentoView, ConsultaRUCView, GenerarComprobanteView, ListarComprobantesView
from django.urls import path

urlpatterns = [
    path('comprobantes/', ListarComprobantesView.as_view(), name='listar-comprobantes'),
    path('comprobantes/generar/<int:venta_id>/', GenerarComprobanteView.as_view(), name='generar-comprobante'),
    path('consulta-dni/<str:dni>/', ConsultaDNIView.as_view(), name='consulta-dni'),
    path('consulta-ruc/<str:ruc>/', ConsultaRUCView.as_view(), name='consulta-ruc'),
    path('consulta-documento/', ConsultaDocumentoView.as_view(), name='consulta-docs'),

]