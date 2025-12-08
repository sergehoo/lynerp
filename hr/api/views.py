# Lyneerp/hr/views.py

import logging
import uuid
from typing import Dict, Any, List, Optional
import pandas as pd
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.db import transaction
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
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
    Interview,
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
    AIProcessingResult,
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
    """
    ViewSet de base multi-tenant :
    - Résout le Tenant à partir de la requête
    - Filtre soit sur `tenant` (FK), soit sur `tenant_id` (CharField)
    """

    def get_tenant(self):
        return get_current_tenant_from_request(self.request)

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return self.queryset.none()

        qs = super().get_queryset() if hasattr(super(), "get_queryset") else self.queryset
        model = qs.model

        # 1) Modèle avec FK Tenant
        if hasattr(model, "tenant"):
            return qs.filter(tenant=tenant)

        # 2) Modèle avec champ tenant_id (CharField)
        if hasattr(model, "tenant_id"):
            # Convention : on stocke de préférence tenant.slug,
            # mais on reste compatible si certains enregistrements contiennent l'UUID.
            slug = getattr(tenant, "slug", None)
            filt = Q(tenant_id=str(tenant.id))
            if slug:
                filt |= Q(tenant_id=slug)
            return qs.filter(filt).distinct()

        # 3) Modèle non-tenantisable
        return qs.none()


# -----------------------------
# Dashboard RH
# -----------------------------
class HRDashboardViewSet(viewsets.ViewSet):
    """Vues pour le tableau de bord RH"""
    permission_classes = [IsAuthenticated, HasRHAccess]

    def get_tenant(self, request) -> Tenant:
        return get_current_tenant_from_request(request)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Récupérer les statistiques du tableau de bord"""
        tenant = self.get_tenant(request)
        tenant_slug = tenant.slug
        if not tenant:
            return Response(
                {"detail": "Tenant introuvable pour cette requête"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant_slug = tenant.slug

        # Models avec tenant = FK(Tenant)
        total_employees = Employee.objects.filter(tenant=tenant).count()
        active_employees = Employee.objects.filter(tenant=tenant, is_active=True).count()

        # Employés en congé aujourd'hui
        today = timezone.now().date()
        employees_on_leave = Employee.objects.filter(
            tenant=tenant,
            is_active=True,
            leaverequest__status='approved',
            leaverequest__start_date__lte=today,
            leaverequest__end_date__gte=today
        ).distinct().count()

        # Nouvelles embauches ce mois-ci
        current_month = today.month
        current_year = today.year
        new_hires_this_month = Employee.objects.filter(
            tenant=tenant,
            hire_date__month=current_month,
            hire_date__year=current_year
        ).count()

        # Models avec tenant_id = CharField
        pending_leave_requests = LeaveRequest.objects.filter(
            tenant_id=tenant_slug,
            status='pending'
        ).count()

        active_recruitments = Recruitment.objects.filter(
            tenant_id=tenant_slug,
            status__in=['OPEN', 'IN_REVIEW', 'INTERVIEW', 'OFFER']
        ).count()

        upcoming_reviews = PerformanceReview.objects.filter(
            tenant_id=tenant_slug,
            review_date__gte=today,
            status='DRAFT'
        ).count()

        stats_data = {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'employees_on_leave': employees_on_leave,
            'new_hires_this_month': new_hires_this_month,
            'pending_leave_requests': pending_leave_requests,
            'active_recruitments': active_recruitments,
            'upcoming_reviews': upcoming_reviews,
        }

        serializer = HRDashboardSerializer(stats_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recruitment_stats(self, request):
        """Statistiques de recrutement"""
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({"detail": "Tenant introuvable"}, status=400)

        tenant_slug = tenant.slug

        total_recruitments = Recruitment.objects.filter(
            tenant_id=tenant_slug
        ).count()

        active_recruitments = Recruitment.objects.filter(
            tenant_id=tenant_slug,
            status__in=['OPEN', 'IN_REVIEW', 'INTERVIEW', 'OFFER']
        ).count()

        total_applications = JobApplication.objects.filter(
            tenant_id=tenant_slug
        ).count()

        applications_this_week = JobApplication.objects.filter(
            tenant_id=tenant_slug,
            applied_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()

        avg_ai_score = JobApplication.objects.filter(
            tenant_id=tenant_slug,
            ai_score__isnull=False
        ).aggregate(avg_score=Avg('ai_score'))['avg_score'] or 0

        apps_by_status = dict(
            JobApplication.objects
            .filter(tenant_id=tenant_slug)
            .values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

        # Conversion : candidatures HIRED / total candidatures
        hires = JobApplication.objects.filter(
            tenant_id=tenant_slug,
            status='HIRED'
        ).count()
        hire_conversion_rate = (hires / total_applications * 100.0) if total_applications > 0 else 0.0

        # Stats IA
        ai_qs = AIProcessingResult.objects.filter(tenant_id=tenant_slug)
        ai_completed = ai_qs.filter(status='COMPLETED').count()
        ai_failed = ai_qs.filter(status='FAILED').count()
        ai_avg_overall = ai_qs.aggregate(a=Avg('overall_match_score'))['a'] or 0.0

        ai_processing_stats = {
            "completed": ai_completed,
            "failed": ai_failed,
            "avg_overall_match_score": round(ai_avg_overall, 2),
        }

        # TODO plus tard : calcul réel du time-to-hire
        average_time_to_hire = 0.0

        stats_data = {
            'total_recruitments': total_recruitments,
            'active_recruitments': active_recruitments,
            'total_applications': total_applications,
            'applications_this_week': applications_this_week,
            'average_ai_score': round(avg_ai_score, 2),
            'hire_conversion_rate': round(hire_conversion_rate, 2),
            'average_time_to_hire': average_time_to_hire,
            'applications_by_status': apps_by_status,
            'ai_processing_stats': ai_processing_stats,
        }

        serializer = RecruitmentStatsSerializer(stats_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def employee_stats(self, request):
        """Statistiques détaillées des employés"""
        tenant = self.get_tenant(request)

        by_department = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .values('department__name')
            .annotate(count=Count('id'))
            .values_list('department__name', 'count')
        )

        by_contract = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .values('contract_type')
            .annotate(count=Count('id'))
            .values_list('contract_type', 'count')
        )

        gender_dist = dict(
            Employee.objects
            .filter(tenant=tenant, is_active=True)
            .exclude(gender='')
            .values('gender')
            .annotate(count=Count('id'))
            .values_list('gender', 'count')
        )

        stats_data = {
            'total_by_department': by_department,
            'total_by_contract_type': by_contract,
            'gender_distribution': gender_dist,
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

class EmployeeViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'matricule']
    ordering_fields = ['first_name', 'last_name', 'hire_date', 'created_at']

    def _resolve_tenant(self):
        """
        Essaie plusieurs sources pour retrouver le tenant :
        - request.tenant (si déjà posé)
        - header X-Tenant-Id (id ou slug)
        """
        request = self.request
        tenant = getattr(request, "tenant", None)

        if tenant:
            return tenant

        header_val = (
                request.headers.get("X-Tenant-Id")
                or request.META.get("HTTP_X_TENANT_ID")
        )
        if not header_val:
            raise ValidationError({"tenant": "Tenant non fourni (X-Tenant-Id manquant)."})

        # selon ton modèle : pk ou slug
        try:
            tenant = Tenant.objects.get(pk=header_val)
        except (Tenant.DoesNotExist, ValueError):
            try:
                tenant = Tenant.objects.get(slug=header_val)
            except Tenant.DoesNotExist:
                raise ValidationError({"tenant": "Tenant invalide pour ce header."})

        return tenant

    def _get_or_create_user_for_employee(self, data):
        """
        Créer ou récupérer un User pour le lier à user_account.
        """
        email = data.get("email")
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""

        if not email:
            return None  # tu peux décider de rendre ça obligatoire si tu veux

        user, _created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,  # ou base sur le matricule
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )
        return user

    def perform_create(self, serializer):
        tenant = self._resolve_tenant()
        user = self._get_or_create_user_for_employee(serializer.validated_data)

        serializer.save(
            tenant=tenant,
            user_account=user,
        )


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

        employees = Employee.objects.filter(id__in=employee_ids, tenant_id=tenant_id)
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
    queryset = Recruitment.objects.all()
    serializer_class = RecruitmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'reference']
    ordering_fields = ['created_at', 'publication_date', 'title']

    # def get_queryset(self):
    #     queryset = super().get_queryset()
    #
    #     filter_serializer = RecruitmentFilterSerializer(data=self.request.query_params)
    #     if filter_serializer.is_valid():
    #         data = filter_serializer.validated_data
    #         filt: Dict[str, Any] = {}
    #
    #         if data.get('status'):
    #             filt['status'] = data['status']
    #
    #         if data.get('department'):
    #             filt['department_id'] = data['department']
    #
    #         if data.get('position'):
    #             filt['position_id'] = data['position']
    #
    #         if data.get('hiring_manager'):
    #             filt['hiring_manager_id'] = data['hiring_manager']
    #
    #         if data.get('publication_date_from'):
    #             filt['publication_date__gte'] = data['publication_date_from']
    #
    #         if data.get('publication_date_to'):
    #             filt['publication_date__lte'] = data['publication_date_to']
    #
    #         queryset = queryset.filter(**filt)
    #
    #     return queryset
    #


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
