from django.urls import path
from .views import (
    CreateTienda, GetAllTiendas, GetTienda, UpdateTienda, UpdateTiendaLogos,
    DeactivateTienda, HabilitarTiendaEliminada, GetMiTiendaView,
    UpdateTiendaStyles, GetPlanosYSuscripcionTienda,
    CreatePlanSuscripcion, ListPlanSuscripcion, ChangePlanTienda,
    UpdatePlanSuscripcion
)

urlpatterns = [
    # Tiendas (superuser)
    path('tiendas/', GetAllTiendas.as_view(), name='get_all_tiendas'),
    path('tiendas/create/', CreateTienda.as_view(), name='create_tienda'),

    # Ver/actualizar tienda
    path('tiendas/<int:id>/', GetTienda.as_view(), name='get_tienda'),
    path('tiendas/update/<int:id>/', UpdateTienda.as_view(), name='update_tienda'),
    path('tiendas/<int:id>/logos/', UpdateTiendaLogos.as_view(), name='update_tienda_logos'),
    path('tiendas/styles/<int:id>/', UpdateTiendaStyles.as_view(), name='update_tienda_styles'),
    path('tiendas/desactivate/<int:id>/', DeactivateTienda.as_view(), name='deactivate_tienda'),
    path('tiendas/habilitar/<int:id>/', HabilitarTiendaEliminada.as_view(), name='habilitar_tienda'),

    # Mi tienda
    path('mi-tienda/', GetMiTiendaView.as_view(), name='get_mi_tienda'),

    # Planes y suscripción de tienda
    path('tiendas/<int:tienda_id>/planes/', GetPlanosYSuscripcionTienda.as_view(), name='get_planes_tienda'),
    path('planes/crear/', CreatePlanSuscripcion.as_view(), name='create_plan'),
    path('planes/', ListPlanSuscripcion.as_view(), name='list_plans'),
    path('planes/<int:plan_id>/', UpdatePlanSuscripcion.as_view(), name='update_plan'),
    path('tiendas/<int:tienda_id>/cambiar-plan/', ChangePlanTienda.as_view(), name='change_plan_tienda'),
]
