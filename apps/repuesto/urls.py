from django.urls import path
from .views import (
    CreateRepuestoAPIView,
    DeleteRepuestoAPIView,
    ListRepuestosAPIView,
    ToggleActiveRepuestoAPIView,
    UpdateRepuestoAPIView,
)

urlpatterns = [
    path("repuestos/", ListRepuestosAPIView.as_view(), name="list_repuestos"),
    path("repuestos/create/", CreateRepuestoAPIView.as_view(), name="create_repuesto"),
    path("repuestos/update/<int:id>/", UpdateRepuestoAPIView.as_view(), name="update_repuesto"),
    path("repuestos/delete/<int:id>/", DeleteRepuestoAPIView.as_view(), name="delete_repuesto"),
    path("repuestos/active/<int:id>/", ToggleActiveRepuestoAPIView.as_view(), name="toggle_active_repuesto"),
]
