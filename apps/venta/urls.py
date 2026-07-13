from django.urls import path

# ANTES: RegistrarVentaView, VentasTotalesPorTiendaView, VentasResumenView,
#        VentaSalesByDateView, ProductosMasVendidosHoyView, VentasPerDayAndMonth,
#        VentaBusquedaView, VentasTotalesHoyView
from apps.venta.views import (
    CreateSaleView,
    SalesTotalsView,
    SalesSummaryView,
    SalesByDateRangeView,
    TopProductsTodayView,
    TopProductsByMonthView,
    SalesByDayMonthView,
    SearchSalesView,
    SalesTodayView,
    PaymentMethodsDistributionView,
    SalesSatisfactionView,
    SalesDailyTrendView,
)

# MAPEO DE CAMBIOS (para frontend):
# RegistrarVentaView        → CreateSaleView         | ventas/crear/          → sales/create/
# VentasTotalesPorTiendaView → SalesTotalsView        | ventas/tienda/         → sales/totals/
# VentasResumenView         → SalesSummaryView        | ventas/resumen/        → sales/summary/
# VentaSalesByDateView      → SalesByDateRangeView    | sales-by-date/         → sales/date-range/
# ProductosMasVendidosHoyView → TopProductsTodayView  | ventas/top-productos-vendidos-hoy/ → sales/top-products/
# VentasPerDayAndMonth      → SalesByDayMonthView     | ventas/resumenbymonthorday/ → sales/by-day-month/
# VentaBusquedaView         → SearchSalesView        | ventas/search/         → sales/search/
# VentasTotalesHoyView      → SalesTodayView          | ventas/hoy/            → sales/today/
# TopProductsByMonthView    → TopProductsByMonthView  | ventas/top-productos-mes/ → sales/top-products-month/

urlpatterns = [
    path('sales/create/',          CreateSaleView.as_view(),          name='create-sale'),
    path('sales/totals/',          SalesTotalsView.as_view(),         name='sales-totals'),
    path('sales/summary/',         SalesSummaryView.as_view(),        name='sales-summary'),
    path('sales/date-range/',      SalesByDateRangeView.as_view(),    name='sales-by-date-range'),
    path('sales/top-products/',    TopProductsTodayView.as_view(),    name='top-products-today'),
    path('sales/top-products-month/', TopProductsByMonthView.as_view(), name='top-products-month'),
    path('sales/by-day-month/',    SalesByDayMonthView.as_view(),     name='sales-by-day-month'),
    path('sales/search/',          SearchSalesView.as_view(),         name='search-sales'),
    path('sales/today/',           SalesTodayView.as_view(),          name='sales-today'),
    path('sales/payment-methods/', PaymentMethodsDistributionView.as_view(), name='payment-methods-distribution'),
    path('sales/satisfaction/',    SalesSatisfactionView.as_view(),         name='sales-satisfaction'),
    path('sales/daily-trend/',     SalesDailyTrendView.as_view(),          name='sales-daily-trend'),
]
