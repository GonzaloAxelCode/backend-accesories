from apps.comprobante.views import  ConsultaDocumentoView,  RegistrarNotaCreditoView
from django.urls import path

urlpatterns = [
    path('consulta-documento/', ConsultaDocumentoView.as_view(), name='consulta-docs'),
    path('nota-credito/registrar/', RegistrarNotaCreditoView.as_view(), name='consulta-docs'),
]