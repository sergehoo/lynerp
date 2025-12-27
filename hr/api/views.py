# Lyneerp/hr/views.py
import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import cache
# from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.db import transaction, IntegrityError, models
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook
from rest_framework import viewsets, status, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.views import APIView
from hr.ai_recruitment_service import AIRecruitmentService
from hr.permissions import HasRHAccess, HasRole

# Models
from hr.models import (
    Department,
    Employee,
    LeaveRequest,
    LeaveType,
    LeaveBalance,
    Position,
    Attendance,
    PerformanceReview,
    JobApplication,
    Recruitment,
    Interview, ContractType, EmploymentContract, ContractAmendment, ContractTemplate, ContractAlert, ContractHistory,
    SalaryHistory, HRDocument, LeaveApprovalStep, HolidayCalendar, Holiday, WorkScheduleTemplate, MedicalRecord,
    MedicalVisit, MedicalRestriction, Payroll, RecruitmentAnalytics, JobOffer, RecruitmentWorkflow, InterviewFeedback,
)

# Serializers
from hr.api.serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
    LeaveBalanceSerializer,
    PositionSerializer,
    AttendanceSerializer,
    PerformanceReviewSerializer,
    JobApplicationSerializer,
    JobApplicationDetailSerializer,
    InterviewSerializer,
    AIProcessingResultSerializer,
    BulkLeaveActionSerializer,
    RecruitmentStatsSerializer,
    HRDashboardSerializer,
    BulkEmployeeActionSerializer,
    EmployeeFilterSerializer,
    EmployeeImportSerializer,
    EmployeeExportSerializer,
    LeaveRequestFilterSerializer,
    EmployeeStatsSerializer,
    RecruitmentSerializer,
    RecruitmentFilterSerializer,
    AIProcessingResult, TenantLiteSerializer, LeaveApprovalStepSerializer, ContractTypeSerializer,
    EmploymentContractSerializer, ContractAmendmentSerializer, ContractTemplateSerializer, ContractAlertSerializer,
    ContractHistorySerializer, SalaryHistorySerializer, HRDocumentSerializer, HolidayCalendarSerializer,
    HolidaySerializer, WorkScheduleTemplateSerializer, MedicalRecordSerializer, MedicalVisitSerializer,
    MedicalRestrictionSerializer, PayrollSerializer, RecruitmentAnalyticsSerializer, JobOfferSerializer,
    RecruitmentWorkflowSerializer, InterviewFeedbackSerializer, EmploymentContractExportSerializer,
)
from tenants.models import Tenant, TenantDomain

# Services (export, etc.)
try:
    from ..services import EmployeeExportService
except Exception:
    # Fallback minimal si le service n'est pas encore implémenté
    class EmployeeExportService:
        def export_employees(self, tenant_id: str, export_format: str, fields: List[str], filters: Dict[str, Any]):
            return {"success": False, "error": "EmployeeExportService non implémenté"}

logger = logging.getLogger(__name__)


def get_current_tenant_from_request(request: HttpRequest) -> Optional[Tenant]:
    """
    Résout le tenant à partir, dans l'ordre :
    1) du token OIDC (request.oidc.tenant / tenant_id : slug ou UUID)
    2) du header X-Tenant-Id : slug ou UUID
    3) du host (TenantDomain ou sous-domaine = slug)
    """

    # 1) Via OIDC (si tu ajoutes oidc au request)
    oidc = getattr(request, "oidc", {}) or {}
    raw = oidc.get("tenant") or oidc.get("tenant_id")
    if raw:
        # slug
        t = Tenant.objects.filter(slug=raw).first()
        if t:
            return t
        # UUID
        try:
            uuid_val = uuid.UUID(str(raw))
            t = Tenant.objects.filter(id=uuid_val).first()
            if t:
                return t
        except ValueError:
            pass

    # 2) Header X-Tenant-Id
    hdr = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
    if hdr:
        t = Tenant.objects.filter(slug=hdr).first()
        if t:
            return t
        try:
            uuid_val = uuid.UUID(str(hdr))
            t = Tenant.objects.filter(id=uuid_val).first()
            if t:
                return t
        except ValueError:
            pass

    # 3) Par le host
    host = request.get_host().split(":")[0].lower()

    # 3.a) TenantDomain direct
    dom = TenantDomain.objects.filter(domain=host).select_related("tenant").first()
    if dom:
        return dom.tenant

    # 3.b) Sous-domaine -> slug
    parts = host.split(".")
    if len(parts) >= 3:
        sub = parts[0]
        t = Tenant.objects.filter(slug=sub).first()
        if t:
            return t

    return None


# -----------------------------
# Mixins multi-tenant
# -----------------------------
class BaseTenantViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # 0) Super admin plateforme : accès global
        if self.request.user and self.request.user.is_superuser:
            return super().get_queryset()

        tenant = self.get_tenant()
        if not tenant:
            return self.queryset.none()

        qs = super().get_queryset()
        model = qs.model

        # FK tenant
        if hasattr(model, "tenant"):
            return qs.filter(tenant=tenant)

        # tenant_id string
        if hasattr(model, "tenant_id"):
            slug = getattr(tenant, "slug", None)
            filt = Q(tenant_id=str(tenant.id))
            if slug:
                filt |= Q(tenant_id=slug)
            return qs.filter(filt).distinct()

        return qs.none()


class HasTenantAccess(BasePermission):
    """
    Autorise:
    - superuser: tout
    - tenant ADMIN/OWNER/HR_BPO selon action
    """
    allowed_roles_read = {"OWNER", "ADMIN", "MANAGER", "HR_BPO", "VIEWER", "MEMBER"}
    allowed_roles_write = {"OWNER", "ADMIN", "HR_BPO"}  # RH externalisée peut créer/modifier RH

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True

        tenant = getattr(view, "get_tenant", lambda: None)()
        # si ton viewset n'a pas get_tenant, tu peux faire:
        # tenant = get_current_tenant_from_request(request)

        if not tenant:
            return False

        membership = get_membership(request.user, tenant)
        if not membership:
            return False

        if request.method in SAFE_METHODS:
            return membership.role in self.allowed_roles_read
        return membership.role in self.allowed_roles_write


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tenant.objects.filter(is_active=True).order_by("name")
    serializer_class = TenantLiteSerializer
    permission_classes = [IsAuthenticated]


# -----------------------------
# Dashboard RH
# -----------------------------
class HRDashboardViewSet(viewsets.ViewSet):
    """Vues pour le tableau de bord RH"""
    permission_classes = [IsAuthenticated, HasRHAccess]

    # -----------------------------
    # Tenant helpers
    # -----------------------------
    def get_tenant(self, request) -> Optional[Tenant]:
        return get_current_tenant_from_request(request)

    def _tenant_filter_q(self, tenant: Tenant) -> Q:
        """
        Pour les modèles qui stockent tenant_id en CharField:
        on accepte à la fois slug et uuid-string (pour compatibilité base).
        """
        q = Q(tenant_id=tenant.slug)
        q |= Q(tenant_id=str(tenant.id))
        return q

    # -----------------------------
    # Dashboard: Stats principales
    # -----------------------------
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Statistiques globales dashboard.
        Optimisé pour gros volume (counts + index).
        """
        tenant = self.get_tenant(request)
        if not tenant:
            return Response(
                {"detail": "Tenant introuvable pour cette requête"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"hr:dash:stats:{tenant.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        today = timezone.localdate()

        # Models avec tenant = FK(Tenant)
        emp_qs = Employee.objects.filter(tenant=tenant)
        total_employees = emp_qs.count()
        active_employees = emp_qs.filter(is_active=True).count()

        employees_on_leave = (
            emp_qs.filter(
                is_active=True,
                leaverequest__status="approved",
                leaverequest__start_date__lte=today,
                leaverequest__end_date__gte=today,
            )
            .distinct()
            .count()
        )

        new_hires_this_month = emp_qs.filter(
            hire_date__year=today.year,
            hire_date__month=today.month,
        ).count()

        # Models avec tenant_id (CharField)
        t_q = self._tenant_filter_q(tenant)

        pending_leave_requests = LeaveRequest.objects.filter(
            t_q,
            status="pending",
        ).count()

        active_recruitments = Recruitment.objects.filter(
            t_q,
            status__in=["OPEN", "IN_REVIEW", "INTERVIEW", "OFFER"],
        ).count()

        upcoming_reviews = PerformanceReview.objects.filter(
            t_q,
            review_date__gte=today,
            status="DRAFT",
        ).count()

        stats_data = {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "employees_on_leave": employees_on_leave,
            "new_hires_this_month": new_hires_this_month,
            "pending_leave_requests": pending_leave_requests,
            "active_recruitments": active_recruitments,
            "upcoming_reviews": upcoming_reviews,
        }

        serializer = HRDashboardSerializer(stats_data)
        data = serializer.data

        cache.set(cache_key, data, 30)  # 30s
        return Response(data)

    # -----------------------------
    # Dashboard: listes légères
    # -----------------------------
    @action(detail=False, methods=["get"])
    def latest_hires(self, request):
        """Top N dernières embauches (léger)"""
        tenant = self.get_tenant(request)
        if not tenant:
            return Response([], status=200)

        try:
            limit = min(int(request.query_params.get("limit", 5)), 50)
        except Exception:
            limit = 5

        qs = (
            Employee.objects
            .filter(tenant=tenant)
            .select_related("department", "position")
            .only("id", "first_name", "last_name", "hire_date", "department__name", "position__title")
            .order_by("-hire_date")[:limit]
        )

        data = [{
            "id": str(e.id),
            "first_name": e.first_name,
            "last_name": e.last_name,
            "hire_date": e.hire_date,
            "department_name": getattr(e.department, "name", None),
            "position_title": getattr(e.position, "title", None),
        } for e in qs]

        return Response(data)

    @action(detail=False, methods=["get"])
    def active_recruitments_list(self, request):
        """Top N recrutements actifs (léger)"""
        tenant = self.get_tenant(request)
        if not tenant:
            return Response([], status=200)

        try:
            limit = min(int(request.query_params.get("limit", 3)), 50)
        except Exception:
            limit = 3

        t_q = self._tenant_filter_q(tenant)

        qs = (
            Recruitment.objects
            .filter(t_q, status__in=["OPEN", "IN_REVIEW", "INTERVIEW", "OFFER"])
            .select_related("department", "position")
            .only(
                "id", "title", "status", "publication_date", "number_of_positions",
                "department__name", "position__title"
            )
            .order_by("-publication_date", "-created_at")[:limit]
        )

        data = [{
            "id": r.id,
            "title": r.title,
            "status": r.status,
            "publication_date": r.publication_date,
            "number_of_positions": r.number_of_positions,
            "department_name": getattr(r.department, "name", None),
            "position_title": getattr(r.position, "title", None),
        } for r in qs]

        return Response(data)

    # -----------------------------
    # Statistiques Recrutement
    # -----------------------------
    @action(detail=False, methods=["get"])
    def recruitment_stats(self, request):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({"detail": "Tenant introuvable"}, status=400)

        cache_key = f"hr:dash:recruitment_stats:{tenant.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        t_q = self._tenant_filter_q(tenant)

        total_recruitments = Recruitment.objects.filter(t_q).count()
        active_recruitments = Recruitment.objects.filter(
            t_q, status__in=["OPEN", "IN_REVIEW", "INTERVIEW", "OFFER"]
        ).count()

        total_applications = JobApplication.objects.filter(t_q).count()

        applications_this_week = JobApplication.objects.filter(
            t_q,
            applied_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()

        avg_ai_score = (
                JobApplication.objects.filter(t_q, ai_score__isnull=False)
                .aggregate(avg_score=Avg("ai_score"))["avg_score"]
                or 0
        )

        apps_by_status = dict(
            JobApplication.objects
            .filter(t_q)
            .values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        hires = JobApplication.objects.filter(t_q, status="HIRED").count()
        hire_conversion_rate = (hires / total_applications * 100.0) if total_applications > 0 else 0.0

        ai_qs = AIProcessingResult.objects.filter(t_q)
        ai_completed = ai_qs.filter(status="COMPLETED").count()
        ai_failed = ai_qs.filter(status="FAILED").count()
        ai_avg_overall = ai_qs.aggregate(a=Avg("overall_match_score"))["a"] or 0.0

        stats_data = {
            "total_recruitments": total_recruitments,
            "active_recruitments": active_recruitments,
            "total_applications": total_applications,
            "applications_this_week": applications_this_week,
            "average_ai_score": round(avg_ai_score, 2),
            "hire_conversion_rate": round(hire_conversion_rate, 2),
            "average_time_to_hire": 0.0,  # TODO
            "applications_by_status": apps_by_status,
            "ai_processing_stats": {
                "completed": ai_completed,
                "failed": ai_failed,
                "avg_overall_match_score": round(ai_avg_overall, 2),
            },
        }

        serializer = RecruitmentStatsSerializer(stats_data)
        data = serializer.data
        cache.set(cache_key, data, 30)
        return Response(data)

    # -----------------------------
    # Stats Employés
    # -----------------------------
    @action(detail=False, methods=["get"])
    def employee_stats(self, request):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({"detail": "Tenant introuvable"}, status=400)

        by_department = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .values("department__name")
            .annotate(count=Count("id"))
            .values_list("department__name", "count")
        )

        by_contract = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .values("contract_type")
            .annotate(count=Count("id"))
            .values_list("contract_type", "count")
        )

        gender_dist = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .exclude(gender="")
            .values("gender")
            .annotate(count=Count("id"))
            .values_list("gender", "count")
        )

        stats_data = {
            "total_by_department": by_department,
            "total_by_contract_type": by_contract,
            "gender_distribution": gender_dist,
        }

        serializer = EmployeeStatsSerializer(stats_data)
        return Response(serializer.data)


# -----------------------------
# Actions en masse
# -----------------------------
class BulkActionsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, HasRHAccess]

    @action(detail=False, methods=['post'])
    def bulk_leave_action(self, request):
        """Action batch sur les demandes de congé"""
        tenant = get_current_tenant_from_request(request)  # 👈
        serializer = BulkLeaveActionSerializer(data=request.data)
        if serializer.is_valid():
            leave_request_ids = serializer.validated_data['leave_request_ids']
            action_type = serializer.validated_data['action']
            reason = serializer.validated_data.get('reason', '')

            leave_requests = LeaveRequest.objects.filter(
                id__in=leave_request_ids,
                tenant_id=tenant.slug,  # 👈 cohérent avec CharField
            )

            updated_count = 0
            with transaction.atomic():
                for leave_request in leave_requests.select_for_update():
                    if action_type == 'approve':
                        leave_request.status = 'approved'
                        leave_request.approved_by = getattr(request.user, "employee_profile", None)
                        leave_request.approved_at = timezone.now()
                    elif action_type == 'reject':
                        leave_request.status = 'rejected'
                        leave_request.rejection_reason = reason
                        leave_request.approved_by = getattr(request.user, "employee_profile", None)
                        leave_request.approved_at = timezone.now()
                    elif action_type == 'cancel':
                        leave_request.status = 'cancelled'

                    leave_request.save()
                    updated_count += 1

            return Response({
                "message": f"{updated_count} demandes de congé mises à jour",
                "action": action_type
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------
# ViewSets RH
# -----------------------------
class DepartmentViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    # permission_classes = [IsAuthenticated, HasRHAccess]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']

    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        """Liste des employés du département"""
        department = self.get_object()
        employees = department.employee_set.filter(is_active=True)
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data)


# class EmployeeViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
#     queryset = Employee.objects.all()
#     serializer_class = EmployeeSerializer
#     permission_classes = [IsAuthenticated]
#     # permission_classes = [IsAuthenticated, HasRHAccess, HasRole]
#     # required_roles = ["hr:view"]
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter]
#     search_fields = ['first_name', 'last_name', 'email', 'matricule']
#     ordering_fields = ['first_name', 'last_name', 'hire_date', 'created_at']
#
#     def get_queryset(self):
#         queryset = super().get_queryset()
#
#         # Filtrage avancé
#         filter_serializer = EmployeeFilterSerializer(data=self.request.query_params)
#         if filter_serializer.is_valid():
#             filt: Dict[str, Any] = {}
#             if filter_serializer.validated_data.get('department'):
#                 filt['department__name'] = filter_serializer.validated_data['department']
#             if filter_serializer.validated_data.get('position'):
#                 filt['position__title'] = filter_serializer.validated_data['position']
#             if filter_serializer.validated_data.get('contract_type'):
#                 filt['contract_type'] = filter_serializer.validated_data['contract_type']
#             if filter_serializer.validated_data.get('is_active') is not None:
#                 filt['is_active'] = filter_serializer.validated_data['is_active']
#             if filter_serializer.validated_data.get('hire_date_from'):
#                 filt['hire_date__gte'] = filter_serializer.validated_data['hire_date_from']
#             if filter_serializer.validated_data.get('hire_date_to'):
#                 filt['hire_date__lte'] = filter_serializer.validated_data['hire_date_to']
#
#             queryset = queryset.filter(**filt)
#
#         return queryset
#
#     @action(detail=False, methods=['post'])
#     def import_employees(self, request):
#         """Import d'employés depuis un fichier CSV/XLSX"""
#         tenant = get_current_tenant_from_request(request)
#         if not tenant:
#             return Response({"detail": "Tenant introuvable"}, status=400)
#
#         serializer = EmployeeImportSerializer(data=request.data)
#         if serializer.is_valid():
#             file = serializer.validated_data['file']
#             update_existing = serializer.validated_data['update_existing']
#
#             try:
#                 if file.name.lower().endswith('.xlsx'):
#                     df = pd.read_excel(file)
#                 else:
#                     df = pd.read_csv(file)
#
#                 imported_count = 0
#                 errors = []
#
#                 with transaction.atomic():
#                     for index, row in df.iterrows():
#                         try:
#                             employee_data = {
#                                 'matricule': row.get('matricule'),
#                                 'first_name': row.get('first_name'),
#                                 'last_name': row.get('last_name'),
#                                 'email': row.get('email'),
#                                 'tenant': tenant,
#                             }
#
#                             if not employee_data['matricule'] or not employee_data['email']:
#                                 raise ValueError("matricule et email sont requis")
#
#                             if update_existing:
#                                 Employee.objects.update_or_create(
#                                     matricule=employee_data['matricule'],
#                                     tenant=tenant,
#                                     defaults=employee_data
#                                 )
#                             else:
#                                 Employee.objects.create(**employee_data)
#
#                             imported_count += 1
#
#                         except Exception as e:
#                             errors.append(f"Ligne {index + 2}: {str(e)}")
#
#                 return Response({
#                     "message": f"{imported_count} employés importés",
#                     "errors": errors
#                 })
#
#             except Exception as e:
#                 return Response(
#                     {"error": f"Erreur lors de l'import: {str(e)}"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     @action(detail=False, methods=['post'])
#     def export_employees(self, request):
#         """Export d'employés"""
#         tenant_id = request.headers.get("X-Tenant-Id")
#         serializer = EmployeeExportSerializer(data=request.data)
#         if serializer.is_valid():
#             export_format = serializer.validated_data['format']
#             fields = serializer.validated_data['fields']
#             filters_data = serializer.validated_data.get('filters', {})
#
#             export_service = EmployeeExportService()
#             result = export_service.export_employees(
#                 tenant_id=tenant_id,
#                 export_format=export_format,
#                 fields=fields,
#                 filters=filters_data
#             )
#
#             if result.get('success'):
#                 return HttpResponse(
#                     result['content'],
#                     content_type=result['content_type'],
#                     headers={'Content-Disposition': f'attachment; filename="{result["filename"]}"'}
#                 )
#             else:
#                 return Response(
#                     {"error": result.get('error', "Export échoué")},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     @action(detail=True, methods=['get'])
#     def leave_balance(self, request, pk=None):
#         """Solde de congés d'un employé"""
#         employee = self.get_object()
#         balances = LeaveBalance.objects.filter(employee=employee)
#         serializer = LeaveBalanceSerializer(balances, many=True)
#         return Response(serializer.data)
#
#     @action(detail=True, methods=['get'])
#     def attendance(self, request, pk=None):
#         """Pointage d'un employé"""
#         employee = self.get_object()
#         month = int(request.query_params.get('month', timezone.now().month))
#         year = int(request.query_params.get('year', timezone.now().year))
#
#         attendances = Attendance.objects.filter(
#             employee=employee,
#             date__year=year,
#             date__month=month
#         )
#         serializer = AttendanceSerializer(attendances, many=True)
#         return Response(serializer.data)

User = get_user_model()

log = logging.getLogger(__name__)
User = get_user_model()


class EmployeeViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'matricule']
    ordering_fields = ['first_name', 'last_name', 'hire_date', 'created_at']

    # ─────────── Utilitaires internes ───────────
    def get_queryset(self):
        qs = Employee.objects.select_related("tenant", "department", "position")

        # ✅ IMPORTANT : si BaseTenantViewSet filtre déjà, garde son comportement.
        # Sinon, applique ton filtre tenant ici (à adapter à ton BaseTenantViewSet)
        tenant = getattr(self.request, "tenant", None)
        if tenant is not None:
            qs = qs.filter(tenant=tenant)

        # --- filtres UI ---
        tenant = self.request.query_params.get("tenant")
        department = self.request.query_params.get("department")
        contract_type = self.request.query_params.get("contract_type")
        is_active = self.request.query_params.get("is_active")

        if department:
            qs = qs.filter(department_id=department)

        if contract_type:
            qs = qs.filter(contract_type=contract_type)

        if is_active not in (None, "",):
            # accepte true/false/1/0
            val = str(is_active).lower()
            if val in ("true", "1", "yes"):
                qs = qs.filter(is_active=True)
            elif val in ("false", "0", "no"):
                qs = qs.filter(is_active=False)

        return qs

    def _get_tenant_kwargs(self):
        request = self.request

        # 1) Si un middleware pose déjà request.tenant
        req_tenant = getattr(request, "tenant", None)
        if req_tenant is not None:
            return {"tenant": req_tenant}

        # 2) Header X-Tenant-Id (slug OU UUID)
        raw = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
        if raw:
            raw = str(raw).strip()
            tenant = None

            # a) Essayer comme UUID (id)
            try:
                uuid.UUID(raw)
                tenant = Tenant.objects.filter(id=raw, is_active=True).first()
            except ValueError:
                # b) Sinon, on considère que c’est un slug
                tenant = Tenant.objects.filter(slug=raw, is_active=True).first()

            if tenant is None:
                raise serializers.ValidationError(
                    {"tenant": f"Tenant introuvable pour « {raw} »."}
                )

            return {"tenant": tenant}

        # 3) Fallback: tenant lié à l'utilisateur (user.employee)
        user = request.user
        if user and not user.is_anonymous:
            emp = getattr(user, "employee", None)
            if emp and emp.tenant_id:
                return {"tenant_id": emp.tenant_id}

        # 4) Rien trouvé → 400 propre
        raise serializers.ValidationError(
            {"tenant": "Impossible de déterminer le tenant pour cette requête."}
        )

    def _get_or_create_user_for_employee(self, validated_data):
        """
        Crée ou récupère un user à partir de l'email de l'employé.
        Compatible avec custom User sans `username`.
        """
        email = validated_data.get("email")
        first_name = validated_data.get("first_name") or ""
        last_name = validated_data.get("last_name") or ""

        if not email:
            return None

        defaults = {
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        }

        # Ajout de username uniquement si le modèle User a ce champ
        if any(f.name == "username" for f in User._meta.get_fields()):
            defaults["username"] = email

        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults=defaults,
            )
            log.debug(
                "[EmployeeViewSet] user_account=%s (created=%s) pour email=%s",
                user, created, email
            )
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email=email).order_by("id").first()
            log.warning(
                "[EmployeeViewSet] Multiple User pour email=%s, on prend le premier id=%s",
                email, user.id if user else None
            )

        return user

    # ─────────── Hooks DRF ───────────
    def _resolve_tenant(self):
        request = self.request

        # 1) Middleware
        req_tenant = getattr(request, "tenant", None)
        if req_tenant is not None:
            return req_tenant

        # 2) Header X-Tenant-Id (slug ou UUID)
        raw = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
        if raw:
            raw = str(raw).strip()
            tenant = None
            try:
                uuid.UUID(raw)
                tenant = Tenant.objects.filter(id=raw, is_active=True).first()
            except ValueError:
                tenant = Tenant.objects.filter(slug=raw, is_active=True).first()

            if tenant is None:
                raise serializers.ValidationError(
                    {"tenant": f"Tenant introuvable pour « {raw} »."}
                )
            return tenant

        # 3) fallback user.employee
        user = request.user
        if user and not user.is_anonymous:
            emp = getattr(user, "employee", None)
            if emp and emp.tenant_id:
                return emp.tenant

        raise serializers.ValidationError(
            {"tenant": "Impossible de déterminer le tenant pour cette requête."}
        )

    def perform_create(self, serializer):
        tenant = self._resolve_tenant()  # ⬅️ objet Tenant
        user = self._get_or_create_user_for_employee(serializer.validated_data)

        extra_kwargs = {"tenant": tenant}
        if user is not None:
            extra_kwargs["user_account"] = user

        with transaction.atomic():
            serializer.save(**extra_kwargs)


class LeaveRequestViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['requested_at', 'start_date']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage avancé
        filter_serializer = LeaveRequestFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filt: Dict[str, Any] = {}
            if filter_serializer.validated_data.get('status'):
                filt['status'] = filter_serializer.validated_data['status']
            if filter_serializer.validated_data.get('employee'):
                filt['employee__id'] = filter_serializer.validated_data['employee']
            if filter_serializer.validated_data.get('leave_type'):
                filt['leave_type__id'] = filter_serializer.validated_data['leave_type']
            if filter_serializer.validated_data.get('start_date_from'):
                filt['start_date__gte'] = filter_serializer.validated_data['start_date_from']
            if filter_serializer.validated_data.get('start_date_to'):
                filt['start_date__lte'] = filter_serializer.validated_data['start_date_to']

            queryset = queryset.filter(**filt)

        return queryset

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        obj.status = "approved"
        obj.approved_by = getattr(request.user, "employee_profile", None)
        obj.approved_at = timezone.now()
        obj.save()
        return Response({"status": obj.status})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self.get_object()
        obj.status = "rejected"
        obj.rejection_reason = request.data.get('reason', '')
        obj.approved_by = getattr(request.user, "employee_profile", None)
        obj.approved_at = timezone.now()
        obj.save()
        return Response({"status": obj.status})


class PositionViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'code']
    ordering_fields = ['title', 'created_at']


class LeaveTypeViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']


class AttendanceViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def bulk_check_in(self, request):
        """
        Pointage massif: body = { "employee_ids": [uuid, ...], "time": "08:30" (optionnel, HH:MM) }
        """
        tenant_id = request.headers.get("X-Tenant-Id")
        employee_ids = request.data.get("employee_ids", [])
        time_str = request.data.get("time")  # "HH:MM"
        if not isinstance(employee_ids, list) or not employee_ids:
            return Response({"detail": "employee_ids requis (liste)"}, status=400)

        today = timezone.localdate()
        check_in_time = None
        if time_str:
            try:
                hh, mm = [int(x) for x in time_str.split(":")]
                check_in_time = timezone.datetime(today.year, today.month, today.day, hh, mm).time()
            except Exception:
                return Response({"detail": "format de time invalide (HH:MM)"}, status=400)

        tenant = get_current_tenant_from_request(request)
        employees = Employee.objects.filter(id__in=employee_ids, tenant=tenant)
        updated = 0
        with transaction.atomic():
            for emp in employees:
                att, _ = Attendance.objects.get_or_create(
                    employee=emp, date=today, defaults={"tenant_id": tenant_id}
                )
                if not att.check_in:
                    att.check_in = check_in_time or timezone.now().time()
                att.status = att.status or 'PRESENT'
                att.save()
                updated += 1
        return Response({"updated": updated})


# -----------------------------
# Recrutement
# -----------------------------

class RecruitmentViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    serializer_class = RecruitmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'reference']
    ordering_fields = ['created_at', 'publication_date', 'title']

    # ---------- Helpers internes ----------

    def _get_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant

        tenant_id = (
                request.headers.get("X-Tenant-Id")
                or request.META.get("HTTP_X_TENANT_ID")
        )
        if not tenant_id:
            return None
        try:
            return Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            return None

    # ---------- Queryset multi-tenant + filtres ----------

    def get_queryset(self):
        request = self.request

        qs = Recruitment.objects.select_related(
            "department", "position", "hiring_manager", "tenant"
        )

        # Filtre tenant
        tenant = self._get_tenant(request)
        if tenant:
            qs = qs.filter(tenant=tenant)
        else:
            # Par sécurité : aucun tenant => aucun résultat au lieu de 500
            return Recruitment.objects.none()

        # Filtres customs (status, department, position, dates)
        status = request.query_params.get("status")
        department = request.query_params.get("department")
        position = request.query_params.get("position")
        pub_from = request.query_params.get("publication_date_from")
        pub_to = request.query_params.get("publication_date_to")

        if status and status != "all":
            qs = qs.filter(status=status)

        if department:
            qs = qs.filter(department_id=department)

        if position:
            qs = qs.filter(position_id=position)

        if pub_from:
            try:
                d = datetime.fromisoformat(pub_from).date()
                qs = qs.filter(publication_date__gte=d)
            except ValueError:
                pass

        if pub_to:
            try:
                d = datetime.fromisoformat(pub_to).date()
                qs = qs.filter(publication_date__lte=d)
            except ValueError:
                pass

        return qs


class RecruitmentStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant

        tenant_id = (
                request.headers.get("X-Tenant-Id")
                or request.META.get("HTTP_X_TENANT_ID")
        )
        if not tenant_id:
            return None
        try:
            return Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        tenant = self._get_tenant(request)
        if not tenant:
            # pas de tenant = pas de data, mais pas 500
            return Response(
                {
                    "total_recruitments": 0,
                    "applications_by_status": {},
                }
            )

        recr_qs = Recruitment.objects.filter(tenant=tenant)

        total_recruitments = recr_qs.count()

        # agrégation par statut de candidatures
        apps_qs = JobApplication.objects.filter(recruitment__in=recr_qs)
        by_status = (
            apps_qs.values("status")
            .annotate(total=models.Count("id"))
            .order_by()
        )
        applications_by_status = {
            row["status"]: row["total"] for row in by_status
        }

        return Response(
            {
                "total_recruitments": total_recruitments,
                "applications_by_status": applications_by_status,
            }
        )


# -----------------------------
# Candidatures (fusion des deux définitions)
# -----------------------------
class JobApplicationViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = JobApplication.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return JobApplicationDetailSerializer
        return JobApplicationSerializer

    @action(detail=True, methods=["post"], url_path="process_ai")
    def process_ai(self, request, pk=None):
        """
        Lance le traitement IA pour cette candidature et retourne le AIProcessingResult.
        """
        tenant_id = request.headers.get("X-Tenant-Id")
        app = get_object_or_404(JobApplication, pk=pk, tenant_id=tenant_id)

        # Idempotence simple : si déjà COMPLETED et pas de forçage → on renvoie le dernier résultat
        force = request.query_params.get("force", "false").lower() == "true"
        existing = getattr(app, "ai_processing", None)
        if existing and existing.status == "COMPLETED" and not force:
            return Response(AIProcessingResultSerializer(existing).data)

        service = AIRecruitmentService()
        result = service.process_application(app)
        return Response(AIProcessingResultSerializer(result).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Changer le statut d'une candidature"""
        application = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = dict(JobApplication.STATUS_CHOICES).keys()
        if new_status in valid_statuses:
            application.status = new_status
            application.save()
            return Response({"status": application.status})

        return Response(
            {"error": "Statut invalide"},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def schedule_interview(self, request, pk=None):
        """Planifier un entretien"""
        application = self.get_object()

        interview_data = {
            'job_application': str(application.id),
            'interview_type': request.data.get('interview_type', 'HR'),
            'scheduled_date': request.data.get('scheduled_date'),
            'duration': request.data.get('duration', 60),
            'interviewers': request.data.get('interviewers', []),
            'tenant_id': application.tenant_id,
        }

        serializer = InterviewSerializer(data=interview_data)
        if serializer.is_valid():
            interview = serializer.save()
            return Response(InterviewSerializer(interview).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InterviewViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Interview.objects.all()
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marquer un entretien comme terminé"""
        interview = self.get_object()

        interview.conducted_at = timezone.now()
        interview.status = 'COMPLETED'
        # feedback structuré json ; overall_rating/recommendation/notes peuvent être fournis
        interview.interviewer_feedback = request.data.get('feedback', {})
        interview.overall_rating = request.data.get('overall_rating')
        interview.recommendation = request.data.get('recommendation', '')
        interview.notes = request.data.get('notes', '')

        interview.save()
        return Response(InterviewSerializer(interview).data)


class PerformanceReviewViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [IsAuthenticated, HasRHAccess]

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        """Finaliser une évaluation"""
        review = self.get_object()
        review.status = 'FINALIZED'
        review.save()
        return Response({"status": review.status})


# ---------- Contrats ----------
class ContractTypeViewSet(BaseTenantViewSet):
    queryset = ContractType.objects.all()
    serializer_class = ContractTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]


EXPORT_FIELD_MAP = {
    # champs simples
    "contract_number": ("contract_number", "N° Contrat"),
    "title": ("title", "Poste"),
    "status": ("status", "Statut"),
    "start_date": ("start_date", "Début"),
    "end_date": ("end_date", "Fin"),
    "base_salary": ("base_salary", "Salaire"),
    "salary_currency": ("salary_currency", "Devise"),
    "weekly_hours": ("weekly_hours", "Heures/sem"),
    "remote_allowed": ("remote_allowed", "Télétravail"),
    "work_location": ("work_location", "Lieu"),

    # relations (valeurs calculées)
    "employee": ("employee__id", "Employé (ID)"),
    "employee_name": (None, "Employé"),
    "department": ("department__name", "Département"),
    "position": ("position__title", "Poste (position)"),
    "contract_type": ("contract_type__name", "Type contrat"),
    "approved_by": ("approved_by__id", "Approuvé par (ID)"),
}


def _bool_to_fr(v):
    return "Oui" if v else "Non"


def _safe_str(v):
    if v is None:
        return ""
    return str(v)


def _format_date(d):
    if not d:
        return ""
    # YYYY-MM-DD (stable pour export)
    return d.isoformat()


class EmploymentContractViewSet(BaseTenantViewSet):
    queryset = EmploymentContract.objects.all()
    serializer_class = EmploymentContractSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["contract_number", "title", "employee__email"]
    ordering_fields = ["start_date", "end_date", "created_at"]

    def _base_queryset_for_export(self, request):
        qs = EmploymentContract.objects.select_related(
            "employee", "department", "position", "contract_type", "approved_by"
        )

        # ✅ Multi-tenant
        tenant_id = getattr(request, "tenant_id", None) or request.headers.get("X-Tenant-Id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        return qs

    def _apply_export_filters(self, qs, filters: dict, search: str, ordering: str):
        # filters attendus (exemples): status, contract_type, department, employee, active_only, date ranges...
        if not filters:
            filters = {}

        # Exemples de filtres
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])

        if filters.get("department"):
            qs = qs.filter(department_id=filters["department"])

        if filters.get("contract_type"):
            qs = qs.filter(contract_type_id=filters["contract_type"])

        if filters.get("employee"):
            qs = qs.filter(employee_id=filters["employee"])

        # date range
        if filters.get("start_date_from"):
            qs = qs.filter(start_date__gte=filters["start_date_from"])
        if filters.get("start_date_to"):
            qs = qs.filter(start_date__lte=filters["start_date_to"])

        # search (simple)
        if search:
            s = search.strip()
            qs = qs.filter(
                Q(contract_number__icontains=s) |
                Q(title__icontains=s) |
                Q(employee__first_name__icontains=s) |
                Q(employee__last_name__icontains=s)
            )

        # ordering (si tu veux autoriser)
        if ordering:
            qs = qs.order_by(ordering)

        return qs

    def _build_rows(self, qs, fields):
        rows = []
        for c in qs:
            row = []
            for f in fields:
                if f not in EXPORT_FIELD_MAP:
                    row.append("")
                    continue

                key, _label = EXPORT_FIELD_MAP[f]

                if f == "employee_name":
                    row.append(_safe_str(f"{c.employee.first_name} {c.employee.last_name}".strip()))
                elif f == "remote_allowed":
                    row.append(_bool_to_fr(bool(c.remote_allowed)))
                elif f in ("start_date", "end_date"):
                    row.append(_format_date(getattr(c, f)))
                elif key:
                    # key de type "department__name" => on lit sur l'objet via relations déjà select_related
                    # comme on a l'objet complet, on préfère l'accès direct:
                    if f == "department":
                        row.append(_safe_str(c.department.name if c.department else ""))
                    elif f == "position":
                        row.append(_safe_str(c.position.title if c.position else ""))
                    elif f == "contract_type":
                        row.append(_safe_str(c.contract_type.name if c.contract_type else ""))
                    else:
                        # champs simples
                        row.append(_safe_str(getattr(c, key.split("__")[0], "")))
                else:
                    row.append("")
            rows.append(row)
        return rows

    def _export_xlsx(self, filename, headers, rows):
        wb = Workbook()
        ws = wb.active
        ws.title = "Contrats"

        ws.append(headers)
        for r in rows:
            ws.append(r)

        # autosize basique
        for col_idx, _ in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(12, min(45, len(str(headers[col_idx - 1])) + 6))

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        resp = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return resp

    def _export_csv(self, filename, headers, rows):
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)

        resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        return resp

    @action(detail=False, methods=["POST"], url_path="export_contracts")
    def export_contracts(self, request, *args, **kwargs):
        ser = EmploymentContractExportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        fmt = ser.validated_data["format"]
        fields = ser.validated_data["fields"]
        filters = ser.validated_data.get("filters") or {}
        ordering = ser.validated_data.get("ordering") or ""
        search = ser.validated_data.get("search") or ""

        # headers
        headers = []
        for f in fields:
            if f in EXPORT_FIELD_MAP:
                headers.append(EXPORT_FIELD_MAP[f][1])
            else:
                headers.append(f)

        qs = self._base_queryset_for_export(request)
        qs = self._apply_export_filters(qs, filters, search, ordering)

        rows = self._build_rows(qs, fields)

        stamp = timezone.now().strftime("%Y%m%d-%H%M")
        filename = f"contracts_export_{stamp}"

        if fmt == "csv":
            return self._export_csv(filename, headers, rows)

        return self._export_xlsx(filename, headers, rows)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        obj = self.get_object()
        obj.status = "ACTIVE"
        obj.save(update_fields=["status"])
        return Response({"status": obj.status})


class ContractAmendmentViewSet(BaseTenantViewSet):
    queryset = ContractAmendment.objects.all()
    serializer_class = ContractAmendmentSerializer
    permission_classes = [IsAuthenticated]


class ContractTemplateViewSet(BaseTenantViewSet):
    queryset = ContractTemplate.objects.all()
    serializer_class = ContractTemplateSerializer
    permission_classes = [IsAuthenticated]


class ContractAlertViewSet(BaseTenantViewSet):
    queryset = ContractAlert.objects.all()
    serializer_class = ContractAlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["due_date", "priority", "created_at"]


class ContractHistoryViewSet(BaseTenantViewSet):
    queryset = ContractHistory.objects.all()
    serializer_class = ContractHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["performed_at"]


# ---------- RH core ----------
class SalaryHistoryViewSet(BaseTenantViewSet):
    queryset = SalaryHistory.objects.all()
    serializer_class = SalaryHistorySerializer
    permission_classes = [IsAuthenticated]


class HRDocumentViewSet(BaseTenantViewSet):
    queryset = HRDocument.objects.all()
    serializer_class = HRDocumentSerializer
    permission_classes = [IsAuthenticated]


# ---------- Congés avancé ----------
class LeaveBalanceViewSet(BaseTenantViewSet):
    queryset = LeaveBalance.objects.all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]


class LeaveApprovalStepViewSet(BaseTenantViewSet):
    queryset = LeaveApprovalStep.objects.all()
    serializer_class = LeaveApprovalStepSerializer
    permission_classes = [IsAuthenticated]


# ---------- Calendrier & horaires ----------
class HolidayCalendarViewSet(BaseTenantViewSet):
    queryset = HolidayCalendar.objects.all()
    serializer_class = HolidayCalendarSerializer
    permission_classes = [IsAuthenticated]


class HolidayViewSet(BaseTenantViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date"]


class WorkScheduleTemplateViewSet(BaseTenantViewSet):
    queryset = WorkScheduleTemplate.objects.all()
    serializer_class = WorkScheduleTemplateSerializer
    permission_classes = [IsAuthenticated]


# ---------- Médical ----------
class MedicalRecordViewSet(BaseTenantViewSet):
    queryset = MedicalRecord.objects.all()
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated]


class MedicalVisitViewSet(BaseTenantViewSet):
    queryset = MedicalVisit.objects.all()
    serializer_class = MedicalVisitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["visit_date", "created_at"]


class MedicalRestrictionViewSet(BaseTenantViewSet):
    queryset = MedicalRestriction.objects.all()
    serializer_class = MedicalRestrictionSerializer
    permission_classes = [IsAuthenticated]


# ---------- Paie ----------
class PayrollViewSet(BaseTenantViewSet):
    queryset = Payroll.objects.all()
    serializer_class = PayrollSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["payroll_number", "employee__email"]
    ordering_fields = ["period_start", "pay_date", "created_at"]


# ---------- Recrutement avancé ----------
class RecruitmentAnalyticsViewSet(BaseTenantViewSet):
    queryset = RecruitmentAnalytics.objects.all()
    serializer_class = RecruitmentAnalyticsSerializer
    permission_classes = [IsAuthenticated]


class JobOfferViewSet(BaseTenantViewSet):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]


class RecruitmentWorkflowViewSet(BaseTenantViewSet):
    queryset = RecruitmentWorkflow.objects.all()
    serializer_class = RecruitmentWorkflowSerializer
    permission_classes = [IsAuthenticated]


class InterviewFeedbackViewSet(BaseTenantViewSet):
    queryset = InterviewFeedback.objects.all()
    serializer_class = InterviewFeedbackSerializer
    permission_classes = [IsAuthenticated]
