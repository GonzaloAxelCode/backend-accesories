from django.urls import path
from .views import (
    CreateTienda, GetAllTiendas, GetTienda, UpdateTienda, UpdateTiendaLogos,
    EliminarTemporalTienda, RestaurarTiendaEliminada, ToggleActivacionTienda,
    GetMiTiendaView,
    UpdateTiendaStyles, GetPlanosYSuscripcionTienda,
    CreatePlanSuscripcion, ListPlanSuscripcion, ChangePlanTienda,
    UpdatePlanSuscripcion, DeletePlanSuscripcion
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
    # Borrado temporal (is_deleted=True + desactiva usuarios)
    path('tiendas/delete/temporal/<int:id>/', EliminarTemporalTienda.as_view(), name='delete_temporal_tienda'),
    # Restaurar borrado temporal (usuarios quedan desactivados)
    path('tiendas/delete/restore/<int:id>/', RestaurarTiendaEliminada.as_view(), name='restore_tienda'),
    # Toggle activar/desactivar sin borrar (POST {"activate": true|false})
    path('tiendas/desactivate/toggle/<int:id>/', ToggleActivacionTienda.as_view(), name='toggle_activacion_tienda'),

    # Mi tienda
    path('mi-tienda/', GetMiTiendaView.as_view(), name='get_mi_tienda'),

    # Planes y suscripción de tienda
    path('tiendas/<int:tienda_id>/planes/', GetPlanosYSuscripcionTienda.as_view(), name='get_planes_tienda'),
    path('planes/crear/', CreatePlanSuscripcion.as_view(), name='create_plan'),
    path('planes/', ListPlanSuscripcion.as_view(), name='list_plans'),
    path('planes/<int:plan_id>/', UpdatePlanSuscripcion.as_view(), name='update_plan'),
    path('planes/eliminar/<int:plan_id>/', DeletePlanSuscripcion.as_view(), name='delete_plan'),
    path('tiendas/<int:tienda_id>/cambiar-plan/', ChangePlanTienda.as_view(), name='change_plan_tienda'),
]
