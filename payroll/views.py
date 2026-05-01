"""Vues web Paie : dashboard, bulletins, périodes."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from payroll.models import PayrollPeriod, Payslip


class PayrollDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "payroll/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            ctx["periods"] = []
            ctx["recent_slips"] = []
            return ctx
        ctx["periods"] = (
            PayrollPeriod.objects.filter(tenant=tenant).order_by("-year", "-month")[:6]
        )
        ctx["recent_slips"] = (
            Payslip.objects.filter(tenant=tenant)
            .select_related("employee", "period")
            .order_by("-created_at")[:10]
        )
        return ctx


class PayslipListView(LoginRequiredMixin, ListView):
    model = Payslip
    template_name = "payroll/payslip_list.html"
    context_object_name = "payslips"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Payslip.objects.none()
        qs = (
            Payslip.objects.filter(tenant=tenant)
            .select_related("employee", "period")
            .order_by("-period__year", "-period__month", "employee__last_name")
        )
        period_id = self.request.GET.get("period")
        if period_id:
            qs = qs.filter(period_id=period_id)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class PayslipDetailView(LoginRequiredMixin, DetailView):
    model = Payslip
    template_name = "payroll/payslip_detail.html"
    context_object_name = "slip"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Payslip.objects.none()
        return (
            Payslip.objects.filter(tenant=tenant)
            .select_related("employee", "period", "employee_profile")
            .prefetch_related("lines", "adjustments")
        )

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
