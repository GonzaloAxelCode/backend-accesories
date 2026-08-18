from django.urls import path
from apps.reports.views import MonthlyReportView, PaymentMethodsByDateRangeView, TopProductsReportView, TopCategoriesReportView

urlpatterns = [
    path("reports/monthly/", MonthlyReportView.as_view(), name="monthly-report"),
    path("reports/payment-methods/", PaymentMethodsByDateRangeView.as_view(), name="payment-methods-report"),
    path("reports/top-products/", TopProductsReportView.as_view(), name="top-products-report"),
    path("reports/top-categories/", TopCategoriesReportView.as_view(), name="top-categories-report"),
]