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
