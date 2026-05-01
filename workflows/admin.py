from __future__ import annotations

from django.contrib import admin

from workflows.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStep,
    ApprovalWorkflow,
    AuditEvent,
    Notification,
)


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0
    fields = ("order", "name", "role_required", "approver", "is_optional")


@admin.register(ApprovalWorkflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "target_model", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("code", "name", "target_model")
    inlines = [ApprovalStepInline]


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "workflow", "status", "current_step", "requested_by", "created_at")
    list_filter = ("tenant", "status", "workflow")
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at", "completed_at")


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ("request", "step", "decided_by", "decision", "decided_at")
    list_filter = ("decision",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "tenant", "level", "channel", "read_at", "created_at")
    list_filter = ("tenant", "level", "channel")
    search_fields = ("title", "user__email")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "tenant", "actor", "severity", "target_model", "created_at")
    list_filter = ("tenant", "severity", "event_type")
    search_fields = ("event_type", "target_id", "description")
    readonly_fields = ("created_at",)
