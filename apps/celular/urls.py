from django.urls import path
from .views import (
    CelularesPorMarcaView,
    TopCostoCompraCelularesView,
    CreateCelularAPIView,
    DeleteCelularAPIView,
    ListCelularesAPIView,
    ToggleActiveCelularAPIView,
    UpdateCelularAPIView,
)

urlpatterns = [
    path("celulares/", ListCelularesAPIView.as_view(), name="list_celulares"),
    path("celulares/por-marca/", CelularesPorMarcaView.as_view(), name="celulares_por_marca"),
    path("celulares/top-costo-compra/", TopCostoCompraCelularesView.as_view(), name="celulares_top_costo_compra"),
    path("celulares/create/", CreateCelularAPIView.as_view(), name="create_celular"),
    path("celulares/update/<int:id>/", UpdateCelularAPIView.as_view(), name="update_celular"),
    path("celulares/delete/<int:id>/", DeleteCelularAPIView.as_view(), name="delete_celular"),
    path("celulares/active/<int:id>/", ToggleActiveCelularAPIView.as_view(), name="toggle_active_celular"),
]
