# Lyneerp/hr/routers.py
from rest_framework.routers import DefaultRouter
from .views import (
    HRDashboardViewSet,
    BulkActionsViewSet,
    DepartmentViewSet,
    EmployeeViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
    PositionViewSet,
    AttendanceViewSet,
    RecruitmentViewSet,
    JobApplicationViewSet,
    InterviewViewSet,
    PerformanceReviewViewSet, TenantViewSet, ContractTypeViewSet, EmploymentContractViewSet, ContractAmendmentViewSet,
    ContractTemplateViewSet, ContractHistoryViewSet, ContractAlertViewSet, SalaryHistoryViewSet, HRDocumentViewSet,
    LeaveBalanceViewSet, LeaveApprovalStepViewSet, HolidayCalendarViewSet, HolidayViewSet, WorkScheduleTemplateViewSet,
    MedicalRecordViewSet, MedicalVisitViewSet, MedicalRestrictionViewSet, PayrollViewSet, RecruitmentAnalyticsViewSet,
    JobOfferViewSet, RecruitmentWorkflowViewSet, InterviewFeedbackViewSet,
)

router = DefaultRouter(trailing_slash=True)

# Dashboard & actions batch (pas de queryset -> basename requis)
router.register(r'dashboard', HRDashboardViewSet, basename='hr-dashboard')
router.register(r'bulk', BulkActionsViewSet, basename='hr-bulk')

# Ressources RH
router.register(r"tenants", TenantViewSet, basename="tenants")
router.register(r'departments', DepartmentViewSet, basename='hr-departments')
router.register(r'employees', EmployeeViewSet, basename='hr-employees')
router.register(r'leave-requests', LeaveRequestViewSet, basename='hr-leave-requests')
router.register(r'leave-types', LeaveTypeViewSet, basename='hr-leave-types')
router.register(r'positions', PositionViewSet, basename='hr-positions')
router.register(r'attendances', AttendanceViewSet, basename='hr-attendances')

# Recrutement
router.register(r'recruitments', RecruitmentViewSet, basename='hr-recruitments')
router.register(r'applications', JobApplicationViewSet, basename='hr-applications')
router.register(r'interviews', InterviewViewSet, basename='hr-interviews')

# Évaluations
router.register(r'performance-reviews', PerformanceReviewViewSet, basename='hr-performance-reviews')

# --- Contrats
router.register(r'contract-types', ContractTypeViewSet, basename='hr-contract-types')
router.register(r'employment-contracts', EmploymentContractViewSet, basename='hr-employment-contracts')
router.register(r'contract-amendments', ContractAmendmentViewSet, basename='hr-contract-amendments')
router.register(r'contract-templates', ContractTemplateViewSet, basename='hr-contract-templates')
router.register(r'contract-alerts', ContractAlertViewSet, basename='hr-contract-alerts')
router.register(r'contract-history', ContractHistoryViewSet, basename='hr-contract-history')

# --- RH core
router.register(r'salary-history', SalaryHistoryViewSet, basename='hr-salary-history')
router.register(r'hr-documents', HRDocumentViewSet, basename='hr-documents')

# --- Congés avancé
router.register(r'leave-balances', LeaveBalanceViewSet, basename='hr-leave-balances')
router.register(r'leave-approval-steps', LeaveApprovalStepViewSet, basename='hr-leave-approval-steps')

# --- Calendrier & horaires
router.register(r'holiday-calendars', HolidayCalendarViewSet, basename='hr-holiday-calendars')
router.register(r'holidays', HolidayViewSet, basename='hr-holidays')
router.register(r'work-schedule-templates', WorkScheduleTemplateViewSet, basename='hr-work-schedule-templates')

# --- Médical
router.register(r'medical-records', MedicalRecordViewSet, basename='hr-medical-records')
router.register(r'medical-visits', MedicalVisitViewSet, basename='hr-medical-visits')
router.register(r'medical-restrictions', MedicalRestrictionViewSet, basename='hr-medical-restrictions')

# --- Paie
router.register(r'payrolls', PayrollViewSet, basename='hr-payrolls')

# --- Recrutement avancé
router.register(r'recruitment-analytics', RecruitmentAnalyticsViewSet, basename='hr-recruitment-analytics')
router.register(r'job-offers', JobOfferViewSet, basename='hr-job-offers')
router.register(r'recruitment-workflows', RecruitmentWorkflowViewSet, basename='hr-recruitment-workflows')
router.register(r'interview-feedbacks', InterviewFeedbackViewSet, basename='hr-interview-feedbacks')
urlpatterns = router.urls
