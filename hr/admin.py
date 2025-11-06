from django.contrib import admin

# Register your models here.
# Lyneerp/hr/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from tenants.models import License, SeatAssignment
from .models import (
    Department, Position, Employee, EmploymentContract, SalaryHistory, HRDocument,
    LeaveType, HolidayCalendar, Holiday, WorkScheduleTemplate, LeaveRequest,
    LeaveBalance, LeaveApprovalStep, Attendance, Payroll, PerformanceReview,
    Recruitment, JobApplication, AIProcessingResult, Interview, InterviewFeedback,
    RecruitmentAnalytics, JobOffer, RecruitmentWorkflow, ContractType, ContractAmendment, ContractTemplate,
    ContractAlert, ContractHistory
)


# === FILTRES PERSONNALISÉS ===
class TenantFilter(admin.SimpleListFilter):
    title = 'Tenant'
    parameter_name = 'tenant'

    def lookups(self, request, model_admin):
        tenants = set([c['tenant'] for c in model_admin.model.objects.values('tenant').distinct()])
        return [(t, t) for t in tenants]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tenant=self.value())
        return queryset


class ActiveFilter(admin.SimpleListFilter):
    title = 'Statut actif'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Actif'),
            ('0', 'Inactif'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_active=True)
        elif self.value() == '0':
            return queryset.filter(is_active=False)
        return queryset


# === INLINES ===
class PositionInline(admin.TabularInline):
    model = Position
    extra = 1
    fields = ['title', 'code', 'level', 'is_active']
    readonly_fields = ['created_at']


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0
    fields = ['matricule', 'first_name', 'last_name', 'email', 'is_active']
    readonly_fields = ['matricule', 'first_name', 'last_name', 'email']
    show_change_link = True
    can_delete = False


# class EmploymentContractInline(admin.TabularInline):
#     model = EmploymentContract
#     extra = 0
#     fields = ['contract_type', 'start_date', 'end_date', 'base_salary']
#     readonly_fields = ['created_at']


class SalaryHistoryInline(admin.TabularInline):
    model = SalaryHistory
    extra = 0
    fields = ['effective_date', 'gross_salary', 'reason']
    readonly_fields = ['created_at']


class HRDocumentInline(admin.TabularInline):
    model = HRDocument
    extra = 0
    fields = ['category', 'title', 'file', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class HolidayInline(admin.TabularInline):
    model = Holiday
    extra = 1
    fields = ['date', 'label']


class LeaveBalanceInline(admin.TabularInline):
    model = LeaveBalance
    extra = 0
    fields = ['leave_type', 'year', 'total_days', 'used_days', 'remaining_days']
    readonly_fields = ['remaining_days']


class LeaveApprovalStepInline(admin.TabularInline):
    model = LeaveApprovalStep
    extra = 0
    fields = ['step', 'approver', 'status', 'decided_at', 'comment']
    readonly_fields = ['decided_at']


class InterviewFeedbackInline(admin.TabularInline):
    model = InterviewFeedback
    extra = 0
    fields = ['interviewer', 'rating', 'summary', 'created_at']
    readonly_fields = ['created_at']


class JobApplicationInline(admin.TabularInline):
    model = JobApplication
    extra = 0
    fields = ['first_name', 'last_name', 'email', 'status', 'ai_score', 'applied_at']
    readonly_fields = ['applied_at']
    show_change_link = True


# === ADMIN CLASSES ===
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'manager', 'employees_count', 'is_active', 'tenant', 'created_at']
    list_filter = [TenantFilter, ActiveFilter, 'created_at']
    search_fields = ['name', 'code', 'description']
    list_select_related = ['parent', 'manager']
    readonly_fields = ['employees_count', 'full_path', 'created_at', 'updated_at']
    fieldsets = [
        ('Informations générales', {
            'fields': ['name', 'code', 'description', 'parent', 'tenant']
        }),
        ('Gestion', {
            'fields': ['manager', 'budget', 'is_active']
        }),
        ('Métadonnées', {
            'fields': ['employees_count', 'full_path', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    inlines = [PositionInline, EmployeeInline]

    def employees_count(self, obj):
        return obj.employees_count

    employees_count.short_description = "Nb employés"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _employees_count=Count('employee')
        ).select_related('parent', 'manager')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['title', 'code', 'department', 'level', 'salary_range', 'is_active', 'tenant']
    list_filter = [TenantFilter, ActiveFilter, 'level', 'department']
    search_fields = ['title', 'code', 'description']
    list_select_related = ['department']
    readonly_fields = ['created_at']
    fieldsets = [
        ('Informations générales', {
            'fields': ['title', 'code', 'department', 'description', 'tenant']
        }),
        ('Grille salariale', {
            'fields': ['salary_min', 'salary_max', 'level']
        }),
        ('Statut', {
            'fields': ['is_active']
        }),
        ('Métadonnées', {
            'fields': ['created_at'],
            'classes': ['collapse']
        })
    ]

    def salary_range(self, obj):
        if obj.salary_min and obj.salary_max:
            return f"{obj.salary_min} - {obj.salary_max}"
        return "-"

    salary_range.short_description = "Échelle salariale"


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['matricule', 'full_name', 'email', 'department', 'position', 'hire_date', 'is_active', 'tenant']
    list_filter = [TenantFilter, ActiveFilter, 'department', 'contract_type', 'work_schedule', 'hire_date']
    search_fields = ['first_name', 'last_name', 'email', 'matricule', 'phone']
    list_select_related = ['department', 'position', 'user_account']
    readonly_fields = ['seniority', 'is_on_leave', 'full_name', 'created_at', 'updated_at']
    fieldsets = [
        ('Informations personnelles', {
            'fields': [
                'matricule', 'first_name', 'last_name', 'email', 'phone',
                'date_of_birth', 'gender', 'address', 'emergency_contact'
            ]
        }),
        ('Informations professionnelles', {
            'fields': [
                'department', 'position', 'hire_date', 'contract_type',
                'work_schedule', 'salary', 'user_account'
            ]
        }),
        ('Statut', {
            'fields': [
                'is_active', 'termination_date', 'termination_reason'
            ]
        }),
        ('Calculs', {
            'fields': ['seniority', 'is_on_leave'],
            'classes': ['collapse']
        }),
        ('Métadonnées', {
            'fields': ['created_at', 'updated_at', 'tenant', 'extra'],
            'classes': ['collapse']
        })
    ]

    # inlines = [EmploymentContractInline, SalaryHistoryInline, HRDocumentInline, LeaveBalanceInline]

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = "Nom complet"
    full_name.admin_order_field = 'first_name'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'department', 'position', 'user_account'
        )


@admin.register(EmploymentContract)
class EmploymentContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 'employee', 'contract_type', 'start_date', 'end_date',
        'status', 'is_active', 'is_probation_period', 'base_salary', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'contract_type', 'start_date', 'department']
    search_fields = ['contract_number', 'employee__first_name', 'employee__last_name']
    list_select_related = ['employee', 'contract_type', 'department', 'position']
    readonly_fields = [
        'is_active', 'is_probation_period', 'days_until_end',
        'contract_duration_days', 'can_be_renewed', 'requires_renewal',
        'created_at', 'updated_at'
    ]
    fieldsets = [
        ('Informations générales', {
            'fields': [
                'contract_number', 'employee', 'contract_type', 'department', 'position', 'tenant'
            ]
        }),
        ('Période du contrat', {
            'fields': [
                'start_date', 'end_date', 'expected_end_date', 'status'
            ]
        }),
        ('Période d\'essai', {
            'fields': [
                'probation_start_date', 'probation_end_date', 'probation_duration_days'
            ],
            'classes': ['collapse']
        }),
        ('Rémunération', {
            'fields': [
                'base_salary', 'salary_currency', 'salary_frequency'
            ]
        }),
        ('Temps de travail', {
            'fields': [
                'weekly_hours', 'work_schedule', 'work_location',
                'remote_allowed', 'remote_days_per_week'
            ],
            'classes': ['collapse']
        }),
        ('Signatures', {
            'fields': [
                'signed_by_employee', 'signed_by_employer', 'signed_date',
                'approved_by', 'approved_at'
            ],
            'classes': ['collapse']
        }),
        ('Résiliation', {
            'fields': [
                'termination_date', 'termination_reason', 'termination_type'
            ],
            'classes': ['collapse']
        }),
        ('Documents', {
            'fields': ['contract_document', 'amendment_document'],
            'classes': ['collapse']
        }),
        ('Statistiques', {
            'fields': [
                'is_active', 'is_probation_period', 'days_until_end',
                'contract_duration_days', 'can_be_renewed', 'requires_renewal'
            ],
            'classes': ['collapse']
        })
    ]
    # inlines = [ContractAmendmentInline, ContractAlertInline, ContractHistoryInline]
    date_hierarchy = 'start_date'
    raw_id_fields = ['employee', 'approved_by', 'department', 'position']

    def is_active(self, obj):
        return obj.is_active

    is_active.boolean = True
    is_active.short_description = "Actif"

    def is_probation_period(self, obj):
        return obj.is_probation_period

    is_probation_period.boolean = True
    is_probation_period.short_description = "Période d'essai"

    def can_be_renewed(self, obj):
        return obj.can_be_renewed

    can_be_renewed.boolean = True
    can_be_renewed.short_description = "Renouvelable"

    def requires_renewal(self, obj):
        return obj.requires_renewal

    requires_renewal.boolean = True
    requires_renewal.short_description = "Nécessite renouvellement"


@admin.register(SalaryHistory)
class SalaryHistoryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'effective_date', 'gross_salary', 'reason', 'tenant']
    list_filter = [TenantFilter, 'effective_date']
    search_fields = ['employee__first_name', 'employee__last_name', 'reason']
    list_select_related = ['employee']
    readonly_fields = ['created_at']
    date_hierarchy = 'effective_date'


@admin.register(HRDocument)
class HRDocumentAdmin(admin.ModelAdmin):
    list_display = ['employee', 'category', 'title', 'uploaded_at', 'tenant']
    list_filter = [TenantFilter, 'category', 'uploaded_at']
    search_fields = ['employee__first_name', 'employee__last_name', 'title']
    list_select_related = ['employee']
    readonly_fields = ['uploaded_at']


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'max_days', 'is_paid', 'requires_approval', 'is_active', 'tenant']
    list_filter = [TenantFilter, ActiveFilter, 'is_paid', 'requires_approval']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at']


@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'tenant']
    list_filter = [TenantFilter, 'country']
    search_fields = ['name']
    inlines = [HolidayInline]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'date', 'label']
    list_filter = ['calendar', 'date']
    search_fields = ['label', 'calendar__name']
    list_select_related = ['calendar']
    date_hierarchy = 'date'


@admin.register(WorkScheduleTemplate)
class WorkScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant']
    list_filter = [TenantFilter]
    search_fields = ['name']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = [
        'employee', 'leave_type', 'start_date', 'end_date', 'number_of_days',
        'status', 'approved_by', 'requested_at', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'leave_type', 'start_date', 'requested_at']
    search_fields = [
        'employee__first_name', 'employee__last_name',
        'leave_type__name', 'reason'
    ]
    list_select_related = ['employee', 'leave_type', 'approved_by']
    readonly_fields = ['requested_at', 'approved_at', 'number_of_days', 'is_approved', 'is_pending']
    fieldsets = [
        ('Informations générales', {
            'fields': ['employee', 'leave_type', 'tenant']
        }),
        ('Période', {
            'fields': ['start_date', 'end_date', 'number_of_days']
        }),
        ('Workflow', {
            'fields': ['status', 'reason', 'approved_by', 'approved_at', 'rejection_reason']
        }),
        ('Fichiers', {
            'fields': ['attachment'],
            'classes': ['collapse']
        }),
        ('Calculs', {
            'fields': ['is_approved', 'is_pending', 'requested_at'],
            'classes': ['collapse']
        })
    ]
    inlines = [LeaveApprovalStepInline]

    def is_approved(self, obj):
        return obj.is_approved

    is_approved.boolean = True
    is_approved.short_description = "Approuvé"

    def is_pending(self, obj):
        return obj.is_pending

    is_pending.boolean = True
    is_pending.short_description = "En attente"


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'year', 'total_days', 'used_days', 'remaining_days', 'utilization_rate']
    list_filter = [TenantFilter, 'year', 'leave_type']
    search_fields = ['employee__first_name', 'employee__last_name', 'leave_type__name']
    list_select_related = ['employee', 'leave_type']
    readonly_fields = ['remaining_days', 'utilization_rate', 'updated_at']

    def utilization_rate(self, obj):
        return f"{obj.utilization_rate:.1f}%"

    utilization_rate.short_description = "Taux utilisation"


@admin.register(LeaveApprovalStep)
class LeaveApprovalStepAdmin(admin.ModelAdmin):
    list_display = ['leave_request', 'step', 'approver', 'status', 'decided_at', 'tenant']
    list_filter = [TenantFilter, 'status', 'step']
    search_fields = ['leave_request__employee__first_name', 'approver__first_name']
    list_select_related = ['leave_request', 'approver']
    readonly_fields = ['decided_at']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in', 'check_out', 'worked_hours', 'status', 'tenant']
    list_filter = [TenantFilter, 'status', 'date']
    search_fields = ['employee__first_name', 'employee__last_name', 'notes']
    list_select_related = ['employee']
    readonly_fields = ['worked_hours', 'overtime_hours', 'created_at', 'updated_at']
    date_hierarchy = 'date'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = [
        'payroll_number', 'employee', 'period_start', 'period_end', 'pay_date',
        'gross_salary', 'net_salary', 'status', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'period_start']
    search_fields = ['employee__first_name', 'employee__last_name', 'payroll_number']
    list_select_related = ['employee']
    readonly_fields = ['gross_salary', 'net_salary', 'created_at', 'updated_at']
    date_hierarchy = 'period_start'
    fieldsets = [
        ('Informations générales', {
            'fields': ['payroll_number', 'employee', 'tenant']
        }),
        ('Période', {
            'fields': ['period_start', 'period_end', 'pay_date']
        }),
        ('Gains', {
            'fields': ['base_salary', 'overtime_pay', 'bonuses', 'allowances']
        }),
        ('Retenues', {
            'fields': ['tax', 'social_security', 'other_deductions']
        }),
        ('Totaux', {
            'fields': ['gross_salary', 'net_salary']
        }),
        ('Statut', {
            'fields': ['status']
        })
    ]


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = [
        'employee', 'reviewer', 'review_date', 'overall_rating',
        'performance_level', 'status', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'review_date']
    search_fields = ['employee__first_name', 'employee__last_name', 'reviewer__first_name']
    list_select_related = ['employee', 'reviewer']
    readonly_fields = ['performance_level', 'created_at', 'updated_at']
    date_hierarchy = 'review_date'

    def performance_level(self, obj):
        return obj.performance_level

    performance_level.short_description = "Niveau performance"


@admin.register(Recruitment)
class RecruitmentAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'reference', 'department', 'position', 'status',
        'publication_date', 'applications_count', 'is_active', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'contract_type', 'publication_date']
    search_fields = ['title', 'reference', 'department__name', 'position__title']
    list_select_related = ['department', 'position', 'hiring_manager']
    readonly_fields = ['applications_count', 'applications_pending_review', 'is_active', 'created_at', 'updated_at']
    filter_horizontal = ['recruiters']
    fieldsets = [
        ('Informations générales', {
            'fields': ['title', 'reference', 'department', 'position', 'tenant']
        }),
        ('Description', {
            'fields': ['job_description', 'requirements']
        }),
        ('Conditions', {
            'fields': [
                'contract_type', 'salary_min', 'salary_max',
                'location', 'remote_allowed', 'number_of_positions'
            ]
        }),
        ('Processus', {
            'fields': ['hiring_manager', 'recruiters']
        }),
        ('Planning', {
            'fields': ['status', 'publication_date', 'closing_date', 'target_hiring_date']
        }),
        ('Configuration IA', {
            'fields': ['ai_scoring_enabled', 'ai_scoring_criteria', 'minimum_ai_score'],
            'classes': ['collapse']
        }),
        ('Statistiques', {
            'fields': ['applications_count', 'applications_pending_review', 'is_active'],
            'classes': ['collapse']
        })
    ]
    inlines = [JobApplicationInline]

    def applications_count(self, obj):
        return obj.applications_count

    applications_count.short_description = "Nb candidatures"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _applications_count=Count('applications')
        ).select_related('department', 'position', 'hiring_manager')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'recruitment', 'status', 'ai_score',
        'is_ai_approved', 'applied_at', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'applied_at']
    search_fields = ['first_name', 'last_name', 'email', 'recruitment__title']
    list_select_related = ['recruitment', 'reviewed_by']
    readonly_fields = [
        'full_name', 'is_ai_approved', 'days_since_application',
        'applied_at', 'reviewed_at', 'updated_at'
    ]
    fieldsets = [
        ('Informations candidat', {
            'fields': ['first_name', 'last_name', 'email', 'phone', 'recruitment', 'tenant']
        }),
        ('Documents', {
            'fields': ['cv', 'cover_letter', 'portfolio']
        }),
        ('Traitement IA', {
            'fields': ['extracted_data', 'ai_score', 'ai_feedback', 'is_ai_approved']
        }),
        ('Workflow', {
            'fields': ['status', 'reviewed_by', 'reviewed_at', 'internal_notes']
        }),
        ('Métadonnées', {
            'fields': ['applied_at', 'days_since_application', 'updated_at'],
            'classes': ['collapse']
        })
    ]

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = "Nom complet"

    def is_ai_approved(self, obj):
        return obj.is_ai_approved

    is_ai_approved.boolean = True
    is_ai_approved.short_description = "Approuvé IA"

    def days_since_application(self, obj):
        return obj.days_since_application

    days_since_application.short_description = "Jours depuis candidature"


@admin.register(AIProcessingResult)
class AIProcessingResultAdmin(admin.ModelAdmin):
    list_display = [
        'job_application', 'status', 'overall_match_score', 'processing_time',
        'processed_at', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'processed_at']
    search_fields = ['job_application__first_name', 'job_application__last_name']
    list_select_related = ['job_application']
    readonly_fields = ['processed_at']
    fieldsets = [
        ('Informations générales', {
            'fields': ['job_application', 'status', 'tenant']
        }),
        ('Données extraites', {
            'fields': [
                'extracted_skills', 'extracted_experience',
                'extracted_education', 'extracted_languages'
            ],
            'classes': ['collapse']
        }),
        ('Scores de matching', {
            'fields': [
                'skills_match_score', 'experience_match_score',
                'education_match_score', 'overall_match_score'
            ]
        }),
        ('Analyse détaillée', {
            'fields': ['missing_skills', 'strong_skills', 'experience_gaps', 'red_flags'],
            'classes': ['collapse']
        }),
        ('Métadonnées', {
            'fields': ['processing_time', 'ai_model_version', 'processed_at', 'error_message'],
            'classes': ['collapse']
        })
    ]


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = [
        'job_application', 'interview_type', 'scheduled_date', 'status',
        'overall_rating', 'is_past_due', 'tenant'
    ]
    list_filter = [TenantFilter, 'interview_type', 'status', 'scheduled_date']
    search_fields = [
        'job_application__first_name', 'job_application__last_name',
        'location', 'meeting_link'
    ]
    list_select_related = ['job_application']
    readonly_fields = ['is_past_due', 'created_at', 'updated_at']
    filter_horizontal = ['interviewers']
    fieldsets = [
        ('Informations générales', {
            'fields': ['job_application', 'interview_type', 'tenant']
        }),
        ('Planning', {
            'fields': ['scheduled_date', 'duration', 'location', 'meeting_link']
        }),
        ('Participants', {
            'fields': ['interviewers']
        }),
        ('Préparation', {
            'fields': ['interview_guide', 'key_points_to_assess'],
            'classes': ['collapse']
        }),
        ('Résultats', {
            'fields': [
                'conducted_at', 'interviewer_feedback', 'overall_rating',
                'recommendation', 'notes', 'status'
            ]
        })
    ]
    inlines = [InterviewFeedbackInline]

    def is_past_due(self, obj):
        return obj.is_past_due

    is_past_due.boolean = True
    is_past_due.short_description = "En retard"


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ['interview', 'interviewer', 'rating', 'created_at', 'tenant']
    list_filter = [TenantFilter, 'created_at']
    search_fields = ['interview__job_application__first_name', 'interviewer__first_name']
    list_select_related = ['interview', 'interviewer']
    readonly_fields = ['created_at']


@admin.register(RecruitmentAnalytics)
class RecruitmentAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'recruitment', 'total_applications', 'hires', 'conversion_rate',
        'ai_efficiency', 'last_calculated', 'tenant'
    ]
    list_filter = [TenantFilter]
    search_fields = ['recruitment__title']
    list_select_related = ['recruitment']
    readonly_fields = [
        'conversion_rate', 'ai_efficiency', 'last_calculated'
    ]

    def conversion_rate(self, obj):
        return f"{obj.conversion_rate:.1f}%"

    conversion_rate.short_description = "Taux conversion"

    def ai_efficiency(self, obj):
        return f"{obj.ai_efficiency:.1f}%"

    ai_efficiency.short_description = "Efficacité IA"


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = [
        'job_application', 'title', 'proposed_salary', 'start_date',
        'status', 'sent_at', 'tenant'
    ]
    list_filter = [TenantFilter, 'status', 'contract_type', 'sent_at']
    search_fields = [
        'job_application__first_name', 'job_application__last_name',
        'title'
    ]
    list_select_related = ['job_application']
    readonly_fields = ['sent_at', 'decided_at', 'created_at']


@admin.register(RecruitmentWorkflow)
class RecruitmentWorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'is_active', 'tenant', 'created_at']
    list_filter = [TenantFilter, 'is_default', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


# === ACTIONS PERSONNALISÉES ===
def activate_selected(modeladmin, request, queryset):
    queryset.update(is_active=True)


activate_selected.short_description = "Activer les éléments sélectionnés"


def deactivate_selected(modeladmin, request, queryset):
    queryset.update(is_active=False)


deactivate_selected.short_description = "Désactiver les éléments sélectionnés"


def approve_leave_requests(modeladmin, request, queryset):
    queryset.update(
        status='approved',
        approved_by=request.user.employee_profile if hasattr(request.user, 'employee_profile') else None,
        approved_at=timezone.now()
    )


approve_leave_requests.short_description = "Approuver les demandes sélectionnées"


def reject_leave_requests(modeladmin, request, queryset):
    queryset.update(status='rejected')


reject_leave_requests.short_description = "Rejeter les demandes sélectionnées"


def publish_recruitments(modeladmin, request, queryset):
    queryset.update(
        status='OPEN',
        publication_date=timezone.now().date()
    )


publish_recruitments.short_description = "Publier les recrutements sélectionnés"


def close_recruitments(modeladmin, request, queryset):
    queryset.update(
        status='CLOSED',
        closing_date=timezone.now().date()
    )


close_recruitments.short_description = "Clôturer les recrutements sélectionnés"


# Lyneerp/hr/admin.py (ajouts)
@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_permanent', 'has_probation', 'is_active', 'tenant']
    list_filter = [TenantFilter, ActiveFilter, 'is_permanent']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']


@admin.register(ContractAmendment)
class ContractAmendmentAdmin(admin.ModelAdmin):
    list_display = ['amendment_number', 'contract', 'amendment_type', 'effective_date', 'status', 'tenant']
    list_filter = [TenantFilter, 'amendment_type', 'status', 'effective_date']
    search_fields = ['amendment_number', 'contract__contract_number']
    list_select_related = ['contract']
    readonly_fields = ['is_effective', 'created_at', 'updated_at']


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'contract_type', 'is_active', 'is_default', 'tenant']
    list_filter = [TenantFilter, ActiveFilter, 'contract_type']
    search_fields = ['name', 'contract_type__name']
    list_select_related = ['contract_type']
    list_editable = ['is_active', 'is_default']


@admin.register(ContractAlert)
class ContractAlertAdmin(admin.ModelAdmin):
    list_display = ['contract', 'alert_type', 'title', 'due_date', 'priority', 'status', 'is_overdue', 'tenant']
    list_filter = [TenantFilter, 'alert_type', 'priority', 'status', 'due_date']
    search_fields = ['title', 'contract__contract_number']
    list_select_related = ['contract', 'assigned_to']
    readonly_fields = ['is_overdue', 'days_until_due', 'created_at', 'updated_at']


@admin.register(ContractHistory)
class ContractHistoryAdmin(admin.ModelAdmin):
    list_display = ['contract', 'action', 'performed_by', 'performed_at', 'tenant']
    list_filter = [TenantFilter, 'action', 'performed_at']
    search_fields = ['contract__contract_number', 'description']
    list_select_related = ['contract', 'performed_by']
    readonly_fields = ['performed_at']
    date_hierarchy = 'performed_at'





# Application des actions aux modèles concernés
DepartmentAdmin.actions = [activate_selected, deactivate_selected]
PositionAdmin.actions = [activate_selected, deactivate_selected]
EmployeeAdmin.actions = [activate_selected, deactivate_selected]
LeaveTypeAdmin.actions = [activate_selected, deactivate_selected]
LeaveRequestAdmin.actions = [approve_leave_requests, reject_leave_requests]
RecruitmentAdmin.actions = [publish_recruitments, close_recruitments]
RecruitmentWorkflowAdmin.actions = [activate_selected, deactivate_selected]

# === CONFIGURATION DU SITE ADMIN ===
admin.site.site_header = "LyneERP - Administration RH"
admin.site.site_title = "LyneERP RH"
admin.site.index_title = "Gestion des Ressources Humaines"
