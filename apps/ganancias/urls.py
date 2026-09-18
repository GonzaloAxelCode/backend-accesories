from django.urls import path

from .views import (
    GananciaRangoView,
    TopProductosMesView,
)

urlpatterns = [
    path("ganancias/rango/", GananciaRangoView.as_view(), name="ganancias-rango"),
    path("ganancias/top-productos-mes/", TopProductosMesView.as_view(), name="ganancias-top-mes"),
]
