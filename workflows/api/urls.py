"""URLs API ``/api/workflows/...`` — minimal pour démarrer."""
from __future__ import annotations

from django.urls import include, path
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from hr.api.views import BaseTenantViewSet
from workflows.models import (
    ApprovalRequest,
    ApprovalWorkflow,
    AuditEvent,
    Notification,
)

app_name = "workflows_api"


class WorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalWorkflow
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class RequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequest
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "completed_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "user"]


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = "__all__"
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class WorkflowViewSet(BaseTenantViewSet):
    queryset = ApprovalWorkflow.objects.all()
    serializer_class = WorkflowSerializer
    permission_classes = [IsAuthenticated]


class RequestViewSet(BaseTenantViewSet):
    queryset = ApprovalRequest.objects.all().select_related("workflow", "requested_by", "current_step")
    serializer_class = RequestSerializer
    permission_classes = [IsAuthenticated]


class NotificationViewSet(BaseTenantViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Un user ne voit QUE ses notifications.
        if not (self.request.user and self.request.user.is_superuser):
            qs = qs.filter(user=self.request.user)
        return qs


class AuditEventViewSet(BaseTenantViewSet):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]


router = DefaultRouter(trailing_slash=True)
router.register(r"workflows", WorkflowViewSet, basename="wf-workflows")
router.register(r"requests", RequestViewSet, basename="wf-requests")
router.register(r"notifications", NotificationViewSet, basename="wf-notifications")
router.register(r"audit", AuditEventViewSet, basename="wf-audit")

urlpatterns = [path("", include(router.urls))]
