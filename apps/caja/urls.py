from django.urls import path
from apps.caja.views import CajaAbiertaView, CerrarCajaView, IniciarCajaView, RealizarGastoView, RealizarIngresoView, RegistrarPrestamoView, ReinicializarCajaView

urlpatterns = [
    path('caja/<int:tienda_id>/', CajaAbiertaView.as_view(), name='caja-abierta'),
    path('create-caja/', IniciarCajaView.as_view(), name='open-caja'), 
    path('caja/realizar-gasto/', RealizarGastoView.as_view(), name='realizar-gasto'),
    path('caja/realizar-ingreso/', RealizarIngresoView.as_view(), name='realizar-ingreso'),
    path('caja/registrar-prestamo/', RegistrarPrestamoView.as_view(), name='registrar-prestamo'),
    path('caja/cerrar/', CerrarCajaView.as_view(), name='cerrar-caja'),
    path('caja/reiniciar/', ReinicializarCajaView.as_view(), name='reiniciar-caja'),
]



