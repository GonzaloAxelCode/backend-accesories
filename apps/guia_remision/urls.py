from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BuscarGuiasRemisionView,
    CrearGuiaRemisionView,
    EnviarGuiaRemisionView,
    GuiaRemisionViewSet,
    ProximoCorrelativoGuiaView,
)

router = DefaultRouter()
router.register(r"guias-remision", GuiaRemisionViewSet, basename="guias-remision")

# OJO: las rutas custom van ANTES del router, si no DRF las captura
# como pk (ej. "search" se interpretaría como id del ViewSet).
urlpatterns = [
    # Listado con filtros + rango de fechas (estilo sales/search/)
    path(
        "guias-remision/search/",
        BuscarGuiasRemisionView.as_view(),
        name="guia-remision-search",
    ),
    # Creación dedicada (con "enviar": true opcional para SUNAT directo)
    path(
        "guias-remision/crear/",
        CrearGuiaRemisionView.as_view(),
        name="guia-remision-crear",
    ),
    path(
        "guias-remision/proximo-correlativo/",
        ProximoCorrelativoGuiaView.as_view(),
        name="guia-remision-correlativo",
    ),
    path("", include(router.urls)),
    path(
        "guias-remision/<int:pk>/enviar/",
        EnviarGuiaRemisionView.as_view(),
        name="guia-remision-enviar",
    ),
    path(
        "guias-remision/enviar/",
        EnviarGuiaRemisionView.as_view(),
        name="guia-remision-enviar-body",
    ),
]
