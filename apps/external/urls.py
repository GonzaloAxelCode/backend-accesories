
from django.urls import path
from .views import ConsultaDNI, ConsultaRUC



urlpatterns = [
    path('api/consulta/dni/<str:dni>/', ConsultaDNI.as_view(), name='consulta_dni'),
    path('api/consulta/ruc/<str:ruc>/', ConsultaRUC.as_view(), name='consulta_ruc'),
]


