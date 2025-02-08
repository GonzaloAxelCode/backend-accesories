from django.urls import path

from apps.venta.views import CancelarVenta,  ListarVentas, ObtenerVenta ,  CrearVenta, VentasPorCliente, VentasPorEstado, VentasPorEstadoPago, VentasPorMetodoPago, VentasPorProducto, VentasPorRangoFechas, VentasPorRangoPrecios, VentasPorTienda, VentasPorVendedor




urlpatterns = [
    path('ventas/', ListarVentas.as_view(), name='listar_ventas'),
    path('ventas/crear/', CrearVenta.as_view(), name='crear_venta'),
    path('ventas/<int:id>/', ObtenerVenta.as_view(), name='obtener_venta'),
    path('ventas/cancelar/<int:id>/', CancelarVenta.as_view(), name='cancelar_venta'),
     path('ventas/crear/', CrearVenta.as_view(), name='crear_venta'),

    # 2. Cancelar venta
    path('ventas/cancelar/<int:id>/', CancelarVenta.as_view(), name='cancelar_venta'),

    # 3. Listar todas las ventas
    path('ventas/', ListarVentas.as_view(), name='listar_ventas'),

    # 4. Obtener detalles de una venta
    path('ventas/<int:id>/', ObtenerVenta.as_view(), name='obtener_venta'),

    # 5. Obtener ventas por fecha
    path('ventas/fecha/', VentasPorRangoFechas.as_view(), name='ventas_por_fecha'),

    # 6. Obtener ventas por rango de precios
    path('ventas/rango_precios/', VentasPorRangoPrecios.as_view(), name='ventas_por_rango_precios'),

    # 7. Obtener ventas por estado de pago
    path('ventas/estado_pago/<str:estado_pago>/', VentasPorEstadoPago.as_view(), name='ventas_por_estado_pago'),

    # 8. Obtener ventas por vendedor
    path('ventas/vendedor/<int:vendedor_id>/', VentasPorVendedor.as_view(), name='ventas_por_vendedor'),

    # 9. Obtener ventas por producto
    path('ventas/producto/', VentasPorProducto.as_view(), name='ventas_por_producto'),

    # 10. Obtener ventas por cliente
    path('ventas/cliente/<int:cliente_id>/', VentasPorCliente.as_view(), name='ventas_por_cliente'),

    # 11. Obtener ventas por tienda
    path('ventas/tienda/', VentasPorTienda.as_view(), name='ventas_por_tienda'),

    # 12. Obtener ventas por metodo de pago
    path('ventas/metodo_pago/', VentasPorMetodoPago.as_view(), name='ventas_por_metodo_pago'),

     # 16. Obtener ventas por rango de fechas
    path('ventas/rango_fechas/', VentasPorRangoFechas.as_view(), name='ventas_por_rango_fechas'),

    # 17. Obtener ventas por producto vendido
    path('ventas/producto_vendido/', VentasPorProducto.as_view(), name='ventas_por_producto_vendido'),

    # 18. Obtener ventas por estado
    path('ventas/estado/<str:estado>/', VentasPorEstado.as_view(), name='ventas_por_estado'),

]

