# Lyneerp/hr/views.py

import logging
from typing import Dict, Any, List
import pandas as pd
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Avg
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
)
from tenants.models import Tenant

# Services (export, etc.)
try:
    from ..services import EmployeeExportService
except Exception:
    # Fallback minimal si le service n'est pas encore implémenté
    class EmployeeExportService:
        def export_employees(self, tenant_id: str, export_format: str, fields: List[str], filters: Dict[str, Any]):
            return {"success": False, "error": "EmployeeExportService non implémenté"}

logger = logging.getLogger(__name__)


def get_current_tenant_from_request(request) -> Tenant:
    tenant_key = (
            request.headers.get("X-Tenant-Id")
            or request.META.get("HTTP_X_TENANT_ID")
            or request.query_params.get("tenant")
    )
    if not tenant_key:
        raise ValidationError("X-Tenant-Id manquant")

    # 1) essayer comme PK int
    try:
        return Tenant.objects.get(pk=int(tenant_key))
    except (ValueError, Tenant.DoesNotExist):
        pass

    # 2) sinon on essaie comme slug
    try:
        return Tenant.objects.get(slug=tenant_key)
    except Tenant.DoesNotExist:
        raise ValidationError(f"Tenant inconnu: {tenant_key}")


# -----------------------------
# Mixins multi-tenant
# -----------------------------
class BaseTenantViewSet:
    """Mixin de base pour filtrer par tenant"""

    def get_tenant(self) -> Tenant:
        if not hasattr(self, "_current_tenant"):
            self._current_tenant = get_current_tenant_from_request(self.request)
        return self._current_tenant

    def get_queryset(self):
        qs = super().get_queryset()
        try:
            tenant = self.get_tenant()
        except ValidationError:
            # pas de tenant → aucune donnée
            return qs.none()

        model = qs.model

        # 1) Modèles avec tenant = ForeignKey(Tenant) : Department, Employee, Position, etc.
        if hasattr(model, "tenant"):
            return qs.filter(tenant=tenant)

        # 2) Modèles avec tenant_id = CharField : LeaveRequest, LeaveType, etc.
        if hasattr(model, "tenant_id"):
            # on choisit de stocker le slug dans les CharField
            return qs.filter(tenant_id=getattr(tenant, "slug", str(tenant.pk)))

        # 3) Fallback : pas de filtrage si pas de notion de tenant
        return qs


# -----------------------------
# Dashboard RH
# -----------------------------

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


class HRDashboardViewSet(viewsets.ViewSet):
    """Vues pour le tableau de bord RH"""
    permission_classes = [IsAuthenticated, HasRHAccess]

    def get_tenant(self, request) -> Tenant:
        # même logique que pour BaseTenantViewSet
        return get_current_tenant_from_request(request)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Récupérer les statistiques du tableau de bord"""
        tenant = self.get_tenant(request)
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

        stats_data = {
            'total_recruitments': total_recruitments,
            'active_recruitments': active_recruitments,
            'total_applications': total_applications,
            'applications_this_week': applications_this_week,
            'average_ai_score': round(avg_ai_score, 2),
            'applications_by_status': apps_by_status,
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


class EmployeeViewSet(BaseTenantViewSet, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    # permission_classes = [IsAuthenticated, HasRHAccess, HasRole]
    required_roles = ["hr:view"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'matricule']
    ordering_fields = ['first_name', 'last_name', 'hire_date', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage avancé
        filter_serializer = EmployeeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filt: Dict[str, Any] = {}
            if filter_serializer.validated_data.get('department'):
                filt['department__name'] = filter_serializer.validated_data['department']
            if filter_serializer.validated_data.get('position'):
                filt['position__title'] = filter_serializer.validated_data['position']
            if filter_serializer.validated_data.get('contract_type'):
                filt['contract_type'] = filter_serializer.validated_data['contract_type']
            if filter_serializer.validated_data.get('is_active') is not None:
                filt['is_active'] = filter_serializer.validated_data['is_active']
            if filter_serializer.validated_data.get('hire_date_from'):
                filt['hire_date__gte'] = filter_serializer.validated_data['hire_date_from']
            if filter_serializer.validated_data.get('hire_date_to'):
                filt['hire_date__lte'] = filter_serializer.validated_data['hire_date_to']

            queryset = queryset.filter(**filt)

        return queryset

    @action(detail=False, methods=['post'])
    def import_employees(self, request):
        """Import d'employés depuis un fichier CSV/XLSX"""
        tenant_id = request.headers.get("X-Tenant-Id")
        serializer = EmployeeImportSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']
            update_existing = serializer.validated_data['update_existing']

            try:
                # Lire le fichier Excel/CSV
                if file.name.lower().endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    df = pd.read_csv(file)

                imported_count = 0
                errors = []

                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            employee_data = {
                                'matricule': row.get('matricule'),
                                'first_name': row.get('first_name'),
                                'last_name': row.get('last_name'),
                                'email': row.get('email'),
                                'tenant_id': tenant_id,
                                # Ajoute d'autres champs si présents dans le fichier...
                            }

                            if not employee_data['matricule'] or not employee_data['email']:
                                raise ValueError("matricule et email sont requis")

                            if update_existing:
                                Employee.objects.update_or_create(
                                    matricule=employee_data['matricule'],
                                    tenant_id=employee_data['tenant_id'],
                                    defaults=employee_data
                                )
                            else:
                                Employee.objects.create(**employee_data)

                            imported_count += 1

                        except Exception as e:
                            errors.append(f"Ligne {index + 2}: {str(e)}")

                return Response({
                    "message": f"{imported_count} employés importés",
                    "errors": errors
                })

            except Exception as e:
                return Response(
                    {"error": f"Erreur lors de l'import: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def export_employees(self, request):
        """Export d'employés"""
        tenant_id = request.headers.get("X-Tenant-Id")
        serializer = EmployeeExportSerializer(data=request.data)
        if serializer.is_valid():
            export_format = serializer.validated_data['format']
            fields = serializer.validated_data['fields']
            filters_data = serializer.validated_data.get('filters', {})

            export_service = EmployeeExportService()
            result = export_service.export_employees(
                tenant_id=tenant_id,
                export_format=export_format,
                fields=fields,
                filters=filters_data
            )

            if result.get('success'):
                return HttpResponse(
                    result['content'],
                    content_type=result['content_type'],
                    headers={'Content-Disposition': f'attachment; filename="{result["filename"]}"'}
                )
            else:
                return Response(
                    {"error": result.get('error', "Export échoué")},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def leave_balance(self, request, pk=None):
        """Solde de congés d'un employé"""
        employee = self.get_object()
        balances = LeaveBalance.objects.filter(employee=employee)
        serializer = LeaveBalanceSerializer(balances, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """Pointage d'un employé"""
        employee = self.get_object()
        month = int(request.query_params.get('month', timezone.now().month))
        year = int(request.query_params.get('year', timezone.now().year))

        attendances = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        )
        serializer = AttendanceSerializer(attendances, many=True)
        return Response(serializer.data)


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
    ordering_fields = ['created_at', 'publication_date']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrage avancé
        filter_serializer = RecruitmentFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filt: Dict[str, Any] = {}
            if filter_serializer.validated_data.get('status'):
                filt['status'] = filter_serializer.validated_data['status']
            if filter_serializer.validated_data.get('department'):
                filt['department__name'] = filter_serializer.validated_data['department']
            if filter_serializer.validated_data.get('position'):
                filt['position__title'] = filter_serializer.validated_data['position']
            if filter_serializer.validated_data.get('hiring_manager'):
                filt['hiring_manager__id'] = filter_serializer.validated_data['hiring_manager']
            if filter_serializer.validated_data.get('publication_date_from'):
                filt['publication_date__gte'] = filter_serializer.validated_data['publication_date_from']
            if filter_serializer.validated_data.get('publication_date_to'):
                filt['publication_date__lte'] = filter_serializer.validated_data['publication_date_to']

            queryset = queryset.filter(**filt)

        return queryset

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publier un recrutement"""
        recruitment = self.get_object()
        recruitment.status = 'OPEN'
        recruitment.publication_date = timezone.now().date()
        recruitment.save()
        return Response({"status": recruitment.status})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Clôturer un recrutement"""
        recruitment = self.get_object()
        recruitment.status = 'CLOSED'
        recruitment.closing_date = timezone.now().date()
        recruitment.save()
        return Response({"status": recruitment.status})


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
