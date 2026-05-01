"""URLs API ``/api/payroll/...``."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payroll.api.ai_views import (
    DetectPayrollAnomaliesView,
    ExplainPayslipView,
    SimulateSalaryView,
)
from payroll.api.views import (
    EmployeePayrollProfileViewSet,
    PayrollAdjustmentViewSet,
    PayrollItemViewSet,
    PayrollJournalViewSet,
    PayrollPeriodViewSet,
    PayrollProfileItemViewSet,
    PayrollProfileViewSet,
    PayslipViewSet,
)

app_name = "payroll_api"

router = DefaultRouter(trailing_slash=True)
router.register(r"items", PayrollItemViewSet, basename="payroll-items")
router.register(r"profiles", PayrollProfileViewSet, basename="payroll-profiles")
router.register(r"profile-items", PayrollProfileItemViewSet, basename="payroll-profile-items")
router.register(r"employee-profiles", EmployeePayrollProfileViewSet, basename="payroll-employee-profiles")
router.register(r"periods", PayrollPeriodViewSet, basename="payroll-periods")
router.register(r"payslips", PayslipViewSet, basename="payroll-payslips")
router.register(r"adjustments", PayrollAdjustmentViewSet, basename="payroll-adjustments")
router.register(r"journals", PayrollJournalViewSet, basename="payroll-journals")

urlpatterns = [
    # Raccourcis IA paie
    path("ai/explain-payslip/", ExplainPayslipView.as_view(), name="ai-explain-payslip"),
    path("ai/detect-anomalies/", DetectPayrollAnomaliesView.as_view(), name="ai-detect-anomalies"),
    path("ai/simulate-salary/", SimulateSalaryView.as_view(), name="ai-simulate-salary"),
    # Routeur DRF
    path("", include(router.urls)),
]
