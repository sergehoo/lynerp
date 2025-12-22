# Lyneerp/hr/views.py (Ajout des vues templates)
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from hr.models import Employee


class HRTemplateView(LoginRequiredMixin, TemplateView):
    """Vue de base pour les templates HR"""

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class HRDashboardView(HRTemplateView):
    template_name = "hr/base.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant_id'] = self.request.headers.get('X-Tenant-Id', 'default')
        return context


class EmployeeManagementView(HRTemplateView):
    template_name = "hr/base.html"


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "hr/employee/detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        # employee.tenant est FK : on fait select_related
        return (
            Employee.objects
            .select_related("tenant", "department", "position", "user_account")
            .prefetch_related(
                "documents",
                "salary_history",
                "contracts",
                "contracts__contract_type",
                "contracts__department",
                "contracts__position",
                "contracts__amendments",
                "contracts__alerts",
                "contracts__history",
                "leavebalance_set" if hasattr(Employee, "leavebalance_set") else "leave_balances",
                "performance_reviews",
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.get_employee()
        tenant_uuid = str(employee.tenant_id)  # UUID (FK Tenant)

        # --- Contrats & parcours ---
        contracts = (
            EmploymentContract.objects
            .select_related("contract_type", "department", "position")
            .filter(employee=employee)
            .order_by("-start_date")
        )

        # --- Congés (demandes) ---
        leaves = (
            LeaveRequest.objects
            .select_related("leave_type")
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-requested_at")[:50]
        )
        leave_balances = (
            LeaveBalance.objects
            .select_related("leave_type")
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-year")
        )

        # --- Absences / Pointage ---
        attendances = (
            Attendance.objects
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-date")[:60]
        )

        # --- Paies ---
        payrolls = (
            Payroll.objects
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-period_start")[:24]
        )

        # --- RH docs / salaire / performance ---
        documents = (
            HRDocument.objects
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-uploaded_at")[:50]
        )
        salary_history = (
            SalaryHistory.objects
            .filter(employee=employee, tenant_id=tenant_uuid)
            .order_by("-effective_date")[:24]
        )
        performance_reviews = (
            PerformanceReview.objects
            .filter(employee=employee, tenant_id=tenant_uuid)
            .select_related("reviewer")
            .order_by("-review_date")[:20]
        )

        # --- Historique “global” : contrats + événements RH (simple) ---
        contract_history = (
            ContractHistory.objects
            .filter(contract__employee=employee, tenant_id=tenant_uuid)
            .select_related("contract", "performed_by")
            .order_by("-performed_at")[:100]
        )

        # --- Médical (protégé) ---
        medical = None
        medical_visits = []
        medical_restrictions = []
        if self.can_view_medical():
            medical = MedicalRecord.objects.filter(employee=employee, tenant_id=tenant_uuid).first()
            medical_visits = MedicalVisit.objects.filter(employee=employee, tenant_id=tenant_uuid).order_by("-visit_date")[:30]
            medical_restrictions = MedicalRestriction.objects.filter(employee=employee, tenant_id=tenant_uuid).order_by("-start_date")[:30]

        ctx.update({
            "tenant": employee.tenant,
            "contracts": contracts,
            "current_contract": employee.current_contract,
            "leaves": leaves,
            "leave_balances": leave_balances,
            "attendances": attendances,
            "payrolls": payrolls,
            "documents": documents,
            "salary_history": salary_history,
            "performance_reviews": performance_reviews,
            "contract_history": contract_history,
            "medical_record": medical,
            "medical_visits": medical_visits,
            "medical_restrictions": medical_restrictions,
            "can_view_medical": self.can_view_medical(),
        })
        return ctx


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    template_name = "hr/employee/form.html"
    success_url = reverse_lazy("hr:employee_list")

    fields = [
        "matricule", "first_name", "last_name", "email",
        "department", "position", "hire_date", "contract_type",
        "date_of_birth", "gender", "phone", "address",
        "salary", "work_schedule",
        "termination_date", "termination_reason",
        "emergency_contact", "extra",
        "is_active",
    ]


class EmployeeDeleteView(LoginRequiredMixin, DeleteView):
    model = Employee
    template_name = "hr/employee/confirm_delete.html"
    success_url = reverse_lazy("hr:employee_list")


class RecruitmentView(HRTemplateView):
    template_name = "hr/base.html"


class LeaveManagementView(HRTemplateView):
    template_name = "hr/base.html"


class AttendanceView(HRTemplateView):
    template_name = "hr/base.html"
