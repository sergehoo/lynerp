"""Vues web du module IA."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from ai_assistant.models import AIAction, AIConversation, AIConversationStatus


class AIPanelView(LoginRequiredMixin, TemplateView):
    """Panel de chat global IA."""

    template_name = "ai_assistant/panel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            ctx["conversations"] = []
            ctx["pending_actions"] = []
            return ctx

        ctx["conversations"] = (
            AIConversation.objects
            .filter(tenant=tenant, user=self.request.user)
            .exclude(status=AIConversationStatus.DELETED)
            .order_by("-updated_at")[:50]
        )
        ctx["pending_actions"] = (
            AIAction.objects
            .filter(tenant=tenant, status="PROPOSED")
            .order_by("-created_at")[:20]
        )
        ctx["module"] = self.request.GET.get("module", "general")
        return ctx


class AIActionListView(LoginRequiredMixin, ListView):
    """Liste des actions IA en attente de validation."""

    model = AIAction
    template_name = "ai_assistant/action_list.html"
    context_object_name = "actions"
    paginate_by = 25

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return AIAction.objects.none()
        qs = AIAction.objects.filter(tenant=tenant).order_by("-created_at")
        status_filter = self.request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AIActionDetailView(LoginRequiredMixin, DetailView):
    model = AIAction
    template_name = "ai_assistant/action_detail.html"
    context_object_name = "action"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return AIAction.objects.none()
        return AIAction.objects.filter(tenant=tenant).select_related("conversation")
