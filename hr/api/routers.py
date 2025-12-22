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
    PerformanceReviewViewSet, TenantViewSet,
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

urlpatterns = router.urls
