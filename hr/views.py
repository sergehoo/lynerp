# Lyneerp/hr/views.py (Ajout des vues templates)
from django.db import models
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from hr.models import Employee, EmploymentContract, LeaveRequest, LeaveBalance, Attendance, Payroll, HRDocument, \
    SalaryHistory, PerformanceReview, ContractHistory, MedicalRecord, MedicalVisit, MedicalRestriction


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


# class EmployeeDetailView(LoginRequiredMixin, DetailView):
#     model = Employee
#     template_name = "hr/employee/detail.html"
#     context_object_name = "employee"
#
#     def get_queryset(self):
#         # employee.tenant est FK : on fait select_related
#         return (
#             Employee.objects
#             .select_related("tenant", "department", "position", "user_account")
#             .prefetch_related(
#                 "documents",
#                 "salary_history",
#                 "contracts",
#                 "contracts__contract_type",
#                 "contracts__department",
#                 "contracts__position",
#                 "contracts__amendments",
#                 "contracts__alerts",
#                 "contracts__history",
#                 "leavebalance_set" if hasattr(Employee, "leavebalance_set") else "leave_balances",
#                 "performance_reviews",
#             )
#         )
#
#     def can_view_medical(self):
#         """
#         À adapter à ta politique:
#         - superuser / staff
#         - ou permission dédiée
#         - ou rôle RH/Médecin
#         """
#         u = self.request.user
#         return u.is_superuser or u.has_perm("hr.view_medical_record")
#
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         employee = self.object
#         tenant_uuid = str(employee.tenant_id)  # UUID (FK Tenant)
#
#         # --- Contrats & parcours ---
#         contracts = (
#             EmploymentContract.objects
#             .select_related("contract_type", "department", "position")
#             .filter(employee=employee)
#             .order_by("-start_date")
#         )
#
#         # --- Congés (demandes) ---
#         leaves = (
#             LeaveRequest.objects
#             .select_related("leave_type")
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-requested_at")[:50]
#         )
#         leave_balances = (
#             LeaveBalance.objects
#             .select_related("leave_type")
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-year")
#         )
#
#         # --- Absences / Pointage ---
#         attendances = (
#             Attendance.objects
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-date")[:60]
#         )
#
#         # --- Paies ---
#         payrolls = (
#             Payroll.objects
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-period_start")[:24]
#         )
#
#         # --- RH docs / salaire / performance ---
#         documents = (
#             HRDocument.objects
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-uploaded_at")[:50]
#         )
#         salary_history = (
#             SalaryHistory.objects
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .order_by("-effective_date")[:24]
#         )
#         performance_reviews = (
#             PerformanceReview.objects
#             .filter(employee=employee, tenant_id=tenant_uuid)
#             .select_related("reviewer")
#             .order_by("-review_date")[:20]
#         )
#
#         # --- Historique “global” : contrats + événements RH (simple) ---
#         contract_history = (
#             ContractHistory.objects
#             .filter(contract__employee=employee, tenant_id=tenant_uuid)
#             .select_related("contract", "performed_by")
#             .order_by("-performed_at")[:100]
#         )
#
#         # --- Médical (protégé) ---
#         medical = None
#         medical_visits = []
#         medical_restrictions = []
#         if self.can_view_medical():
#             medical = MedicalRecord.objects.filter(employee=employee, tenant_id=tenant_uuid).first()
#             medical_visits = MedicalVisit.objects.filter(employee=employee, tenant_id=tenant_uuid).order_by(
#                 "-visit_date")[:30]
#             medical_restrictions = MedicalRestriction.objects.filter(employee=employee, tenant_id=tenant_uuid).order_by(
#                 "-start_date")[:30]
#
#         ctx.update({
#             "tenant": employee.tenant,
#             "contracts": contracts,
#             "current_contract": employee.current_contract,
#             "leaves": leaves,
#             "leave_balances": leave_balances,
#             "attendances": attendances,
#             "payrolls": payrolls,
#             "documents": documents,
#             "salary_history": salary_history,
#             "performance_reviews": performance_reviews,
#             "contract_history": contract_history,
#             "medical_record": medical,
#             "medical_visits": medical_visits,
#             "medical_restrictions": medical_restrictions,
#             "can_view_medical": self.can_view_medical(),
#         })
#         return ctx

class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = "hr/employee/detail.html"
    context_object_name = "employee"

    # ⚠️ IMPORTANT : si multi-tenant strict, filtre ici par tenant résolu depuis la requête
    def get_queryset(self):
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
                # "skills",
                "performance_reviews",
            )
        )

    def can_view_medical(self):
        u = self.request.user
        return u.is_superuser or u.has_perm("hr.view_medical_record")

    # ----------------------------
    # Helpers
    # ----------------------------
    def _paginate(self, qs, page_param: str, per_page: int = 20):
        p = Paginator(qs, per_page)
        page_number = self.request.GET.get(page_param, 1)
        return p.get_page(page_number)

    def calculate_employee_stats(self, employee, tenant_id_str):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        last_30_days_worked = Attendance.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            date__gte=today - timedelta(days=30),
            status="PRESENT",
        ).count()

        late_arrivals_month = Attendance.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            date__gte=month_start,
        ).count()

        absences_year = Attendance.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            date__gte=year_start,
            status__in=["ABSENT", "SICK_LEAVE"],
        ).count()

        overtime_month = Attendance.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            date__gte=month_start,
        ).aggregate(total=Sum("overtime_hours"))["total"] or 0

        total_leave_used = LeaveRequest.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            status="APPROVED",
            start_date__year=today.year,
        ).aggregate(total=Sum("number_of_days"))["total"] or 0

        return {
            "last_30_days_worked": last_30_days_worked,
            "late_arrivals_month": late_arrivals_month,
            "absences_year": absences_year,
            "overtime_month": overtime_month,
            "total_leave_used": total_leave_used,
        }

    def get_upcoming_deadlines(self, employee, tenant_id_str):
        deadlines = []
        today = date.today()

        current = getattr(employee, "current_contract", None)
        contract_for_probation = current or employee.contracts.order_by("-start_date").first()

        if contract_for_probation and contract_for_probation.probation_end_date:
            pe = contract_for_probation.probation_end_date
            if pe > today:
                days_left = (pe - today).days
                if days_left <= 30:
                    deadlines.append({
                        "type": "Fin période essai",
                        "date": pe,
                        "description": f"Fin de période d'essai dans {days_left} jours",
                        "priority": "high" if days_left <= 7 else "medium",
                    })

        ending_contracts = EmploymentContract.objects.filter(
            employee=employee,
            tenant_id=tenant_id_str,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=90),
        ).order_by("end_date")

        for c in ending_contracts:
            days_left = (c.end_date - today).days
            deadlines.append({
                "type": "Fin de contrat",
                "date": c.end_date,
                "description": f"Contrat {c.contract_number} se termine dans {days_left} jours",
                "priority": "high" if days_left <= 30 else "medium",
            })

        deadlines.sort(key=lambda x: x["date"])
        return deadlines[:8]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.object

        # ⚠️ IMPORTANT : selon ton schéma, tenant_id est slug ou uuid. Ici on utilise string.
        tenant_id_str = str(employee.tenant_id)
        current_year = timezone.now().year

        # --- Query params (recherche légère par onglet) ---
        q_contracts = (self.request.GET.get("q_contracts") or "").strip()
        q_leaves = (self.request.GET.get("q_leaves") or "").strip()
        q_payroll = (self.request.GET.get("q_payroll") or "").strip()
        q_docs = (self.request.GET.get("q_docs") or "").strip()
        q_att = (self.request.GET.get("q_att") or "").strip()

        # --- CONTRATS (tout, paginé) ---
        contracts_qs = (
            EmploymentContract.objects
            .select_related("contract_type", "department", "position")
            .filter(employee=employee, tenant_id=tenant_id_str)
            .order_by("-start_date")
        )
        if q_contracts:
            contracts_qs = contracts_qs.filter(
                Q(contract_number__icontains=q_contracts) |
                Q(contract_type__name__icontains=q_contracts) |
                Q(position__title__icontains=q_contracts)
            )

        # --- CONGÉS (tout, paginé) ---
        leaves_qs = (
            LeaveRequest.objects
            .select_related("leave_type")
            .filter(employee=employee, tenant_id=tenant_id_str)
            .order_by("-requested_at")
        )
        if q_leaves:
            leaves_qs = leaves_qs.filter(
                Q(leave_type__name__icontains=q_leaves) |
                Q(status__icontains=q_leaves)
            )

        leave_balances_qs = (
            LeaveBalance.objects
            .select_related("leave_type")
            .filter(employee=employee, tenant_id=tenant_id_str, year=current_year)
            .order_by("leave_type__name")
        )

        # --- POINTAGE (tout, paginé) ---
        attendances_qs = (
            Attendance.objects
            .filter(employee=employee, tenant_id=tenant_id_str)
            .order_by("-date")
        )
        if q_att:
            attendances_qs = attendances_qs.filter(Q(status__icontains=q_att))

        # --- PAIE (tout, paginé) ---
        payrolls_qs = (
            Payroll.objects
            .filter(employee=employee, tenant_id=tenant_id_str)
            .order_by("-period_start")
        )
        if q_payroll:
            payrolls_qs = payrolls_qs.filter(Q(reference__icontains=q_payroll))

        # --- DOCUMENTS (tout, paginé) ---
        documents_qs = (
            HRDocument.objects
            .filter(employee=employee, tenant_id=tenant_id_str)
            .order_by("-uploaded_at")
        )
        if q_docs:
            documents_qs = documents_qs.filter(Q(title__icontains=q_docs) | Q(doc_type__icontains=q_docs))

        # --- SALAIRE & PERF (tout, paginé) ---
        salary_history_qs = SalaryHistory.objects.filter(
            employee=employee, tenant_id=tenant_id_str
        ).order_by("-effective_date")

        performance_reviews_qs = (
            PerformanceReview.objects
            .filter(employee=employee, tenant_id=tenant_id_str)
            .select_related("reviewer")
            .order_by("-review_date")
        )

        contract_history_qs = (
            ContractHistory.objects
            .filter(contract__employee=employee, tenant_id=tenant_id_str)
            .select_related("contract", "performed_by")
            .order_by("-performed_at")
        )

        # --- MEDICAL (protégé, paginé) ---
        medical = None
        medical_visits_qs = MedicalVisit.objects.none()
        medical_restrictions_qs = MedicalRestriction.objects.none()
        if self.can_view_medical():
            medical = MedicalRecord.objects.filter(employee=employee, tenant_id=tenant_id_str).first()
            medical_visits_qs = MedicalVisit.objects.filter(employee=employee, tenant_id=tenant_id_str).order_by("-visit_date")
            medical_restrictions_qs = MedicalRestriction.objects.filter(employee=employee, tenant_id=tenant_id_str).order_by("-start_date")

        stats = self.calculate_employee_stats(employee, tenant_id_str)
        upcoming_deadlines = self.get_upcoming_deadlines(employee, tenant_id_str)

        # --- Pagination (par onglet) ---
        contracts_page = self._paginate(contracts_qs, "page_contracts", per_page=10)
        leaves_page = self._paginate(leaves_qs, "page_leaves", per_page=10)
        attendances_page = self._paginate(attendances_qs, "page_att", per_page=15)
        payrolls_page = self._paginate(payrolls_qs, "page_payroll", per_page=12)
        documents_page = self._paginate(documents_qs, "page_docs", per_page=12)

        salary_history_page = self._paginate(salary_history_qs, "page_salary", per_page=10)
        performance_reviews_page = self._paginate(performance_reviews_qs, "page_perf", per_page=10)
        contract_history_page = self._paginate(contract_history_qs, "page_hist", per_page=15)

        medical_visits_page = self._paginate(medical_visits_qs, "page_med_visits", per_page=10) if self.can_view_medical() else None
        medical_restrictions_page = self._paginate(medical_restrictions_qs, "page_med_rest", per_page=10) if self.can_view_medical() else None

        ctx.update({
            "tenant": employee.tenant,
            "current_contract": getattr(employee, "current_contract", None),

            "current_year": current_year,
            "stats": stats,
            "upcoming_deadlines": upcoming_deadlines,
            "can_view_medical": self.can_view_medical(),
            "medical_record": medical,

            # pages
            "contracts_page": contracts_page,
            "leaves_page": leaves_page,
            "attendances_page": attendances_page,
            "payrolls_page": payrolls_page,
            "documents_page": documents_page,

            "leave_balances": leave_balances_qs,

            "salary_history_page": salary_history_page,
            "performance_reviews_page": performance_reviews_page,
            "contract_history_page": contract_history_page,

            "medical_visits_page": medical_visits_page,
            "medical_restrictions_page": medical_restrictions_page,

            # query strings to keep filters
            "q_contracts": q_contracts,
            "q_leaves": q_leaves,
            "q_payroll": q_payroll,
            "q_docs": q_docs,
            "q_att": q_att,
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
