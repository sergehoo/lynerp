"""Vues web CRM (dashboard + listes)."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.views.generic import ListView, TemplateView

from crm.models import Account, Lead, Opportunity, OpportunityStatus, Pipeline


class CRMDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "crm/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return ctx

        ctx["accounts_count"] = Account.objects.filter(tenant=tenant, is_active=True).count()
        ctx["leads_new"] = Lead.objects.filter(tenant=tenant, status="NEW").count()

        agg = Opportunity.objects.filter(
            tenant=tenant, status=OpportunityStatus.OPEN,
        ).aggregate(total=Sum("amount"), weighted=Sum("amount"))
        ctx["pipeline_total"] = agg["total"] or 0

        ctx["pipelines"] = (
            Pipeline.objects.filter(tenant=tenant, is_active=True)
            .prefetch_related("stages__opportunities")
        )
        ctx["recent_opportunities"] = (
            Opportunity.objects.filter(tenant=tenant)
            .select_related("account", "stage")
            .order_by("-updated_at")[:10]
        )
        return ctx


class LeadListView(LoginRequiredMixin, ListView):
    template_name = "crm/lead_list.html"
    context_object_name = "leads"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Lead.objects.none()
        qs = Lead.objects.filter(tenant=tenant)
        s = self.request.GET.get("status")
        if s:
            qs = qs.filter(status=s)
        return qs.order_by("-created_at")


class OpportunityListView(LoginRequiredMixin, ListView):
    template_name = "crm/opportunity_list.html"
    context_object_name = "opportunities"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Opportunity.objects.none()
        qs = (
            Opportunity.objects.filter(tenant=tenant)
            .select_related("account", "stage", "pipeline")
        )
        s = self.request.GET.get("status")
        if s:
            qs = qs.filter(status=s)
        return qs.order_by("-updated_at")
