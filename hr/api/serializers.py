# Lyneerp/hr/serializers.py
from django.contrib.auth.models import User
from rest_framework import serializers
from hr.models import (
    Department, Employee, LeaveRequest, AIProcessingResult,
    Position, LeaveType, LeaveBalance, Attendance, Payroll,
    PerformanceReview, Recruitment, JobApplication, Interview,
    RecruitmentAnalytics, RecruitmentWorkflow, InterviewFeedback, JobOffer, MedicalRestriction, MedicalVisit,
    MedicalRecord, WorkScheduleTemplate, Holiday, HolidayCalendar, LeaveApprovalStep, HRDocument, SalaryHistory,
    ContractHistory, ContractAlert, ContractTemplate, ContractAmendment, EmploymentContract, ContractType
)
from django.utils import timezone

from tenants.models import Tenant


class DepartmentSerializer(serializers.ModelSerializer):
    employees_count = serializers.ReadOnlyField()
    full_path = serializers.ReadOnlyField()
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)

    class Meta:
        model = Department
        fields = [
            "id", "name", "parent", "code", "description", "manager", "manager_name",
            "budget", "is_active", "created_at", "updated_at", "tenant_id",
            "employees_count", "full_path"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "employees_count", "full_path"]


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    current_employees_count = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "id", "title", "code", "department", "department_name", "description",
            "salary_min", "salary_max", "level", "is_active", "created_at", "tenant_id",
            "current_employees_count"
        ]
        read_only_fields = ["id", "created_at", "current_employees_count"]

    def get_current_employees_count(self, obj):
        return obj.employees.filter(is_active=True).count()


# class EmployeeSerializer(serializers.ModelSerializer):
#     department_name = serializers.CharField(source='department.name', read_only=True)
#     position_title = serializers.CharField(source='position.title', read_only=True)
#     full_name = serializers.ReadOnlyField()
#     seniority = serializers.ReadOnlyField()
#     is_on_leave = serializers.ReadOnlyField()
#
#     class Meta:
#         model = Employee
#         fields = [
#             "id", "matricule", "first_name", "last_name", "full_name", "email",
#             "department", "department_name", "position", "position_title",
#             "hire_date", "contract_type", "date_of_birth", "gender", "phone",
#             "address", "emergency_contact", "salary", "work_schedule",
#             "is_active", "termination_date", "termination_reason",
#             "user_account", "extra", "tenant_id", "created_at", "updated_at",
#             "seniority", "is_on_leave"
#         ]
#         read_only_fields = ["id", "created_at", "updated_at", "full_name", "seniority", "is_on_leave"]

class TenantLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_title = serializers.CharField(source='position.title', read_only=True)
    full_name = serializers.ReadOnlyField()
    seniority = serializers.ReadOnlyField()
    is_on_leave = serializers.ReadOnlyField()
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)

    def validate_email(self, value):
        existing_user = User.objects.filter(email=value).first()
        if not existing_user:
            return value

        from hr.models import Employee

        # si on édite un employé déjà lié à ce user → OK
        if self.instance and self.instance.user_account_id == existing_user.id:
            return value

        if Employee.objects.filter(user_account=existing_user).exists():
            raise serializers.ValidationError(
                "Un employé est déjà lié à cet utilisateur."
            )
        return value

    class Meta:
        model = Employee
        fields = [
            "id", "matricule", "first_name", "last_name", "full_name", "email",
            "department", "department_name", "position", "position_title",
            "hire_date", "contract_type", "date_of_birth", "gender", "phone",
            "address", "emergency_contact", "salary", "work_schedule",
            "is_active", "termination_date", "termination_reason",
            "user_account", "extra", "created_at", "updated_at",
            "tenant", "tenant_name", "tenant_slug", "seniority", "is_on_leave",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "full_name", "seniority", "is_on_leave",
            "user_account",  # géré côté backend
            "tenant_name", "tenant_slug",
        ]
        extra_kwargs = {
            "date_of_birth": {"required": False, "allow_null": True},
            "gender": {"required": False},
            "phone": {"required": False},
            "address": {"required": False},
            "emergency_contact": {"required": False, "allow_null": True},
            "salary": {"required": False, "allow_null": True},
            "termination_date": {"required": False, "allow_null": True},
            "termination_reason": {"required": False},
            "extra": {"required": False, "allow_null": True},
        }


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id", "name", "code", "description", "max_days", "is_paid",
            "requires_approval", "carry_over", "carry_over_max", "is_active",
            "created_at", "tenant_id"
        ]
        read_only_fields = ["id", "created_at"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    remaining_days = serializers.ReadOnlyField()
    utilization_rate = serializers.ReadOnlyField()

    class Meta:
        model = LeaveBalance
        fields = [
            "id", "employee", "employee_name", "leave_type", "leave_type_name",
            "year", "total_days", "used_days", "carried_over_days",
            "remaining_days", "utilization_rate", "updated_at", "tenant_id"
        ]
        read_only_fields = ["id", "updated_at", "remaining_days", "utilization_rate"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    is_approved = serializers.ReadOnlyField()
    is_pending = serializers.ReadOnlyField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "employee", "employee_name", "leave_type", "leave_type_name",
            "start_date", "end_date", "number_of_days", "reason", "status",
            "requested_at", "approved_by", "approved_by_name", "approved_at",
            "rejection_reason", "attachment", "tenant_id",
            "is_approved", "is_pending"
        ]
        read_only_fields = [
            "id", "requested_at", "approved_at", "is_approved", "is_pending"
        ]

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("La date de fin doit être après la date de début.")

        # Vérifier que la demande ne chevauche pas une autre demande approuvée
        if self.instance and self.instance.status == 'approved':
            return data

        employee = data.get('employee') or (self.instance and self.instance.employee)
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        overlapping_requests = LeaveRequest.objects.filter(
            employee=employee,
            status='approved',
            start_date__lte=end_date,
            end_date__gte=start_date
        )

        if self.instance:
            overlapping_requests = overlapping_requests.exclude(id=self.instance.id)

        if overlapping_requests.exists():
            raise serializers.ValidationError("Une demande de congé approuvée existe déjà pour cette période.")

        return data


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id", "employee", "employee_name", "date", "check_in", "check_out",
            "worked_hours", "overtime_hours", "status", "notes", "tenant_id",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "worked_hours", "overtime_hours"]

    def validate(self, data):
        if data.get('check_out') and data.get('check_in'):
            if data['check_out'] <= data['check_in']:
                raise serializers.ValidationError("L'heure de sortie doit être après l'heure d'arrivée.")
        return data


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_matricule = serializers.CharField(source='employee.matricule', read_only=True)

    class Meta:
        model = Payroll
        fields = [
            "id", "employee", "employee_name", "employee_matricule",
            "period_start", "period_end", "pay_date", "base_salary",
            "overtime_pay", "bonuses", "allowances", "tax", "social_security",
            "other_deductions", "gross_salary", "net_salary", "status",
            "payroll_number", "tenant_id", "created_at", "updated_at"
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "gross_salary", "net_salary"
        ]


class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)
    performance_level = serializers.ReadOnlyField()

    class Meta:
        model = PerformanceReview
        fields = [
            "id", "employee", "employee_name", "reviewer", "reviewer_name",
            "review_period_start", "review_period_end", "review_date",
            "overall_rating", "goals_achievement", "strengths",
            "areas_for_improvement", "goals_next_period", "status",
            "performance_level", "tenant_id", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "performance_level"]

    def validate(self, data):
        if data['review_period_start'] > data['review_period_end']:
            raise serializers.ValidationError("La période d'évaluation est invalide.")

        if data['review_date'] < data['review_period_end']:
            raise serializers.ValidationError("La date d'évaluation doit être après la fin de la période d'évaluation.")

        return data


class RecruitmentSerializer(serializers.ModelSerializer):
    # Champs dérivés pour le front
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True)

    applications_count = serializers.SerializerMethodField()
    applications_pending_review = serializers.SerializerMethodField()

    class Meta:
        model = Recruitment
        fields = "__all__"
        read_only_fields = (
            "tenant",
            "status",
            "created_at",
            "updated_at",
            "applications_count",
            "applications_pending_review",
        )

    # Helpers internes
    def _get_tenant(self):
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError({"tenant": "Contexte requête manquant."})

        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant

        # Header envoyé par ton front
        tenant_id = (
                request.headers.get("X-Tenant-Id")
                or request.META.get("HTTP_X_TENANT_ID")
        )
        if tenant_id:
            try:
                return Tenant.objects.get(pk=tenant_id)
            except Tenant.DoesNotExist:
                raise serializers.ValidationError({"tenant": "Tenant introuvable."})

        raise serializers.ValidationError({"tenant": "Tenant non fourni."})

    def _get_employee(self):
        request = self.context.get("request")
        if not request:
            return None
        employee = getattr(request.user, "employee", None)
        return employee

    # Exposition des propriétés
    def get_applications_count(self, obj):
        # propriété du modèle => jamais d'AttributeError
        return obj.applications_count

    def get_applications_pending_review(self, obj):
        return obj.applications_pending_review

    def create(self, validated_data):
        # facultatif → dict vide par défaut
        validated_data.setdefault("requirements", {})

        # tenant injecté automatiquement
        validated_data["tenant"] = self._get_tenant()

        # manager par défaut = employee du user courant si non fourni
        if not validated_data.get("hiring_manager"):
            employee = self._get_employee()
            if employee:
                validated_data["hiring_manager"] = employee

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # On ne laisse pas le client changer le tenant
        validated_data.pop("tenant", None)
        return super().update(instance, validated_data)


class JobApplicationSerializer(serializers.ModelSerializer):
    recruitment_title = serializers.CharField(source='recruitment.title', read_only=True)
    full_name = serializers.ReadOnlyField()
    is_ai_approved = serializers.ReadOnlyField()
    days_since_application = serializers.ReadOnlyField()

    class Meta:
        model = JobApplication
        fields = [
            "id", "recruitment", "recruitment_title", "first_name", "last_name",
            "full_name", "email", "phone", "cv", "cover_letter", "portfolio",
            "extracted_data", "ai_score", "ai_feedback", "status", "applied_at",
            "reviewed_by", "reviewed_at", "internal_notes", "tenant_id",
            "updated_at", "is_ai_approved", "days_since_application"
        ]
        read_only_fields = [
            "id", "applied_at", "updated_at", "is_ai_approved",
            "days_since_application"
        ]

    def create(self, validated_data):
        # Appeler le service IA pour traiter la candidature
        instance = super().create(validated_data)

        # Démarrer le traitement IA si activé
        if instance.recruitment.ai_scoring_enabled:
            from .services.ai_recruitment_service import AIRecruitmentService
            ai_service = AIRecruitmentService()
            ai_service.process_application(instance)

        return instance


class JobApplicationDetailSerializer(JobApplicationSerializer):
    """Sérialiseur détaillé avec les résultats IA complets"""
    ai_processing = serializers.SerializerMethodField()
    interview_count = serializers.SerializerMethodField()

    class Meta(JobApplicationSerializer.Meta):
        fields = JobApplicationSerializer.Meta.fields + ["ai_processing", "interview_count"]

    def get_ai_processing(self, obj):
        try:
            ai_result = obj.ai_processing
            return AIProcessingResultSerializer(ai_result).data
        except AIProcessingResult.DoesNotExist:
            return None

    def get_interview_count(self, obj):
        return obj.interviews.count()


class AIProcessingResultSerializer(serializers.ModelSerializer):
    job_application_details = serializers.SerializerMethodField()

    class Meta:
        model = AIProcessingResult
        fields = [
            "id", "job_application", "job_application_details", "status",
            "processed_at", "processing_time", "ai_model_version",
            "extracted_skills", "extracted_experience", "extracted_education",
            "extracted_languages", "skills_match_score", "experience_match_score",
            "education_match_score", "overall_match_score", "missing_skills",
            "strong_skills", "experience_gaps", "red_flags", "error_message",
        ]
        read_only_fields = ["id", "processed_at"]

    def get_job_application_details(self, obj):
        return {
            "full_name": obj.job_application.full_name,
            "email": obj.job_application.email,
            "recruitment_title": obj.job_application.recruitment.title
        }


class InterviewSerializer(serializers.ModelSerializer):
    job_application_details = serializers.SerializerMethodField()
    interviewers_names = serializers.SerializerMethodField()
    candidate_name = serializers.CharField(source='candidate.full_name', read_only=True)
    is_past_due = serializers.ReadOnlyField()

    class Meta:
        model = Interview
        fields = [
            "id", "job_application", "job_application_details", "interview_type",
            "interviewers", "interviewers_names", "candidate", "candidate_name",
            "scheduled_date", "duration", "location", "meeting_link",
            "interview_guide", "key_points_to_assess", "conducted_at",
            "interviewer_feedback", "overall_rating", "recommendation",
            "notes", "status", "tenant_id", "created_at", "updated_at", "is_past_due"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_past_due"]

    def get_job_application_details(self, obj):
        return {
            "full_name": obj.job_application.full_name,
            "email": obj.job_application.email,
            "recruitment_title": obj.job_application.recruitment.title
        }

    def get_interviewers_names(self, obj):
        return [interviewer.full_name for interviewer in obj.interviewers.all()]

    def validate(self, data):
        if data.get('scheduled_date'):
            if data['scheduled_date'] <= timezone.now():
                raise serializers.ValidationError("La date de l'entretien doit être dans le futur.")
        return data


class RecruitmentAnalyticsSerializer(serializers.ModelSerializer):
    recruitment_title = serializers.CharField(source='recruitment.title', read_only=True)
    conversion_rate = serializers.ReadOnlyField()
    ai_efficiency = serializers.ReadOnlyField()

    class Meta:
        model = RecruitmentAnalytics
        fields = [
            "id", "recruitment", "recruitment_title", "total_applications",
            "ai_screened_applications", "ai_rejected_applications",
            "hr_reviewed_applications", "interviews_scheduled", "offers_made",
            "hires", "average_processing_time", "time_to_hire",
            "ai_accuracy_rate", "ai_false_positives", "ai_false_negatives",
            "application_sources", "last_calculated", "tenant_id",
            "conversion_rate", "ai_efficiency"
        ]
        read_only_fields = ["id", "last_calculated", "conversion_rate", "ai_efficiency"]


class RecruitmentWorkflowSerializer(serializers.ModelSerializer):
    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = RecruitmentWorkflow
        fields = [
            "id", "name", "description", "stages", "ai_scoring_weights",
            "email_templates", "is_default", "is_active", "tenant_id",
            "created_at", "updated_at", "usage_count"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "usage_count"]

    def get_usage_count(self, obj):
        return Recruitment.objects.filter(
            tenant_id=obj.tenant_id,
            # On suppose qu'un champ workflow existe dans Recruitment
            # workflow=obj
        ).count()


# Sérialiseurs pour les statistiques et tableaux de bord
class HRDashboardSerializer(serializers.Serializer):
    total_employees = serializers.IntegerField()
    active_employees = serializers.IntegerField()
    employees_on_leave = serializers.IntegerField()
    new_hires_this_month = serializers.IntegerField()

    turnover_rate = serializers.FloatField(required=False, default=0.0)
    average_tenure = serializers.FloatField(required=False, default=0.0)

    pending_leave_requests = serializers.IntegerField()
    approved_leave_this_month = serializers.IntegerField(required=False, default=0)

    active_recruitments = serializers.IntegerField()
    total_applications = serializers.IntegerField(required=False, default=0)
    applications_this_month = serializers.IntegerField(required=False, default=0)

    upcoming_reviews = serializers.IntegerField()
    average_performance_rating = serializers.FloatField(required=False, default=0.0)


class RecruitmentStatsSerializer(serializers.Serializer):
    total_recruitments = serializers.IntegerField()
    active_recruitments = serializers.IntegerField()
    total_applications = serializers.IntegerField()
    applications_this_week = serializers.IntegerField()
    average_ai_score = serializers.FloatField()
    hire_conversion_rate = serializers.FloatField(required=False, default=0.0)
    average_time_to_hire = serializers.FloatField(required=False, default=0.0)
    applications_by_status = serializers.DictField()
    ai_processing_stats = serializers.DictField(required=False, default=dict)


class EmployeeStatsSerializer(serializers.Serializer):
    """Statistiques des employés"""
    total_by_department = serializers.DictField()
    total_by_position = serializers.DictField()
    total_by_contract_type = serializers.DictField()
    gender_distribution = serializers.DictField()
    average_salary_by_department = serializers.DictField()
    turnover_by_month = serializers.DictField()


# Sérialiseurs pour les filtres et recherches
class EmployeeFilterSerializer(serializers.Serializer):
    """Sérialiseur pour filtrer les employés"""
    department = serializers.IntegerField(required=False)
    # department = serializers.CharField(required=False)
    position = serializers.CharField(required=False)
    contract_type = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)
    hire_date_from = serializers.DateField(required=False)
    hire_date_to = serializers.DateField(required=False)


class RecruitmentFilterSerializer(serializers.Serializer):
    """Sérialiseur pour filtrer les recrutements"""
    status = serializers.CharField(required=False)
    department = serializers.CharField(required=False)
    position = serializers.CharField(required=False)
    hiring_manager = serializers.CharField(required=False)
    publication_date_from = serializers.DateField(required=False)
    publication_date_to = serializers.DateField(required=False)


class LeaveRequestFilterSerializer(serializers.Serializer):
    """Sérialiseur pour filtrer les demandes de congé"""
    status = serializers.CharField(required=False)
    employee = serializers.CharField(required=False)
    leave_type = serializers.CharField(required=False)
    start_date_from = serializers.DateField(required=False)
    start_date_to = serializers.DateField(required=False)


# Sérialiseurs pour les imports/exports
class EmployeeImportSerializer(serializers.Serializer):
    """Sérialiseur pour l'import d'employés"""
    file = serializers.FileField()
    update_existing = serializers.BooleanField(default=False)


class EmployeeExportSerializer(serializers.Serializer):
    """Sérialiseur pour l'export d'employés"""
    format = serializers.ChoiceField(choices=['csv', 'excel', 'pdf'])
    fields = serializers.ListField(child=serializers.CharField())
    filters = EmployeeFilterSerializer(required=False)


# Sérialiseurs pour les actions batch
class BulkLeaveActionSerializer(serializers.Serializer):
    """Sérialiseur pour les actions batch sur les congés"""
    leave_request_ids = serializers.ListField(
        child=serializers.UUIDField()
    )
    action = serializers.ChoiceField(choices=['approve', 'reject', 'cancel'])
    reason = serializers.CharField(required=False)


class BulkEmployeeActionSerializer(serializers.Serializer):
    """Sérialiseur pour les actions batch sur les employés"""
    employee_ids = serializers.ListField(
        child=serializers.UUIDField()
    )
    action = serializers.ChoiceField(choices=[
        'activate', 'deactivate', 'terminate', 'change_department'
    ])
    data = serializers.DictField(required=False)


class ContractTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractType
        fields = "__all__"


class EmploymentContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentContract
        fields = "__all__"


class ContractAmendmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractAmendment
        fields = "__all__"


class ContractTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTemplate
        fields = "__all__"


class ContractAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractAlert
        fields = "__all__"


class ContractHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractHistory
        fields = "__all__"


class SalaryHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryHistory
        fields = "__all__"


class HRDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HRDocument
        fields = "__all__"


class LeaveApprovalStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveApprovalStep
        fields = "__all__"


class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = "__all__"


class MedicalVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalVisit
        fields = "__all__"


class MedicalRestrictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRestriction
        fields = "__all__"


class JobOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOffer
        fields = "__all__"


class HolidayCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayCalendar
        fields = "__all__"


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"

class WorkScheduleTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkScheduleTemplate
        fields = "__all__"

class InterviewFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewFeedback
        fields = "__all__"
