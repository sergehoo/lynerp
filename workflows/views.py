"""Vues web Workflows / Notifications."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from workflows.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Notification,
)
from workflows.services import approve_step, reject_step


class ApprovalRequestListView(LoginRequiredMixin, ListView):
    template_name = "workflows/request_list.html"
    context_object_name = "requests"
    paginate_by = 25

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return ApprovalRequest.objects.none()
        qs = (
            ApprovalRequest.objects.filter(tenant=tenant)
            .select_related("workflow", "current_step", "requested_by")
            .order_by("-created_at")
        )
        status_filter = self.request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ApprovalRequestDetailView(LoginRequiredMixin, DetailView):
    template_name = "workflows/request_detail.html"
    context_object_name = "request_obj"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return ApprovalRequest.objects.none()
        return (
            ApprovalRequest.objects.filter(tenant=tenant)
            .select_related("workflow", "current_step", "requested_by")
            .prefetch_related("decisions__decided_by", "workflow__steps")
        )


class ApprovalActionView(LoginRequiredMixin, View):
    """POST simple pour approuver/rejeter via formulaire."""

    def post(self, request, pk):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return HttpResponseForbidden()
        req = get_object_or_404(ApprovalRequest, tenant=tenant, pk=pk)
        action = request.POST.get("action")
        comment = (request.POST.get("comment") or "").strip()

        try:
            if action == "approve":
                approve_step(request=req, decided_by=request.user, comment=comment)
            elif action == "reject":
                reject_step(request=req, decided_by=request.user, comment=comment)
        except Exception as exc:  # noqa: BLE001
            return redirect(f"/workflows/requests/{pk}/?error={exc}")
        return redirect(f"/workflows/requests/{pk}/")


class NotificationInboxView(LoginRequiredMixin, ListView):
    template_name = "workflows/notifications.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Notification.objects.none()
        return (
            Notification.objects
            .filter(tenant=tenant, user=self.request.user)
            .order_by("-created_at")
        )


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return HttpResponseForbidden()
        notif = get_object_or_404(
            Notification, tenant=tenant, user=request.user, pk=pk,
        )
        if notif.read_at is None:
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at"])
        return redirect(request.META.get("HTTP_REFERER", "/workflows/notifications/"))


class AuditFeedView(LoginRequiredMixin, ListView):
    template_name = "workflows/audit_feed.html"
    context_object_name = "events"
    paginate_by = 50

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return AuditEvent.objects.none()
        qs = AuditEvent.objects.filter(tenant=tenant).select_related("actor")
        sev = self.request.GET.get("severity")
        if sev:
            qs = qs.filter(severity=sev)
        return qs.order_by("-created_at")
