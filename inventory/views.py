"""Vues web Stock."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import ListView, TemplateView

from inventory.models import Article, Inventory, StockAlert, StockAlertStatus


class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return ctx
        ctx["total_articles"] = Article.objects.filter(tenant=tenant, is_active=True).count()
        ctx["total_stock_value"] = (
            Inventory.objects.filter(tenant=tenant)
            .aggregate(s=Sum("quantity"))["s"] or 0
        )
        ctx["open_alerts"] = (
            StockAlert.objects.filter(tenant=tenant, status=StockAlertStatus.OPEN)
            .select_related("article", "warehouse")
            .order_by("-created_at")[:20]
        )
        ctx["low_stock_articles"] = (
            Inventory.objects.filter(tenant=tenant, quantity__lte=0)
            .select_related("article", "warehouse")[:20]
        )
        return ctx


class ArticleListView(LoginRequiredMixin, ListView):
    template_name = "inventory/article_list.html"
    context_object_name = "articles"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Article.objects.none()
        qs = Article.objects.filter(tenant=tenant).select_related("category")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(sku__icontains=q) | qs.filter(name__icontains=q)
        return qs.order_by("sku")


class StockAlertListView(LoginRequiredMixin, ListView):
    template_name = "inventory/alert_list.html"
    context_object_name = "alerts"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return StockAlert.objects.none()
        qs = StockAlert.objects.filter(tenant=tenant).select_related("article", "warehouse")
        status_filter = self.request.GET.get("status", "OPEN")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-created_at")
