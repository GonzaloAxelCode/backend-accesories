from django.urls import path
from apps.reports.views import DailySummaryReportView, MonthlyReportView, PaymentMethodsByDateRangeView, TopProductsReportView, TopCategoriesReportView, DailyPaymentMethodsReportView, DailyPeakHoursReportView, DailyTopProductsReportView, DailyTopCategoriesReportView, DailyRecentSalesReportView, DailyCustomersReportView, MonthlyCustomersReportView

urlpatterns = [
    path("reports/daily-summary/", DailySummaryReportView.as_view(), name="daily-summary-report"),
    path("reports/daily-payment-methods/", DailyPaymentMethodsReportView.as_view(), name="daily-payment-methods-report"),
    path("reports/daily-peak-hours/", DailyPeakHoursReportView.as_view(), name="daily-peak-hours-report"),
    path("reports/daily-top-products/", DailyTopProductsReportView.as_view(), name="daily-top-products-report"),
    path("reports/daily-top-categories/", DailyTopCategoriesReportView.as_view(), name="daily-top-categories-report"),
    path("reports/daily-recent-sales/", DailyRecentSalesReportView.as_view(), name="daily-recent-sales-report"),
    path("reports/daily-customers/", DailyCustomersReportView.as_view(), name="daily-customers-report"),
    path("reports/monthly-customers/", MonthlyCustomersReportView.as_view(), name="monthly-customers-report"),
    path("reports/monthly/", MonthlyReportView.as_view(), name="monthly-report"),
    path("reports/payment-methods/", PaymentMethodsByDateRangeView.as_view(), name="payment-methods-report"),
    path("reports/top-products/", TopProductsReportView.as_view(), name="top-products-report"),
    path("reports/top-categories/", TopCategoriesReportView.as_view(), name="top-categories-report"),
]