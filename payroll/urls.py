"""URLs web Paie ``/payroll/...``."""
from __future__ import annotations

from django.urls import path

from payroll.views import (
    PayrollDashboardView,
    PayslipDetailView,
    PayslipListView,
)

app_name = "payroll"

urlpatterns = [
    path("", PayrollDashboardView.as_view(), name="dashboard"),
    path("payslips/", PayslipListView.as_view(), name="payslip-list"),
    path("payslips/<uuid:pk>/", PayslipDetailView.as_view(), name="payslip-detail"),
]
