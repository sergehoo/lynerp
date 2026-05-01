from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from reporting.services import compute, list_kpis


class ReportingDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "reporting/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        kpis = []
        if tenant is not None:
            for code in [
                "hr.headcount", "hr.new_hires_30d",
                "payroll.total_net_last_period",
                "crm.pipeline_open_amount",
                "inventory.open_alerts",
                "projects.active_count",
                "ai.actions_pending",
            ]:
                kpis.append({"code": code, "data": compute(code, tenant=tenant)})
        ctx["kpis"] = kpis
        ctx["available_kpis"] = list_kpis()
        return ctx
