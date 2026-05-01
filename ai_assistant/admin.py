from __future__ import annotations

from django.contrib import admin

from ai_assistant.models import (
    AIAction,
    AIAuditLog,
    AIConversation,
    AIMessage,
    AIModelConfig,
    AIPromptTemplate,
    AIToolCall,
)


@admin.register(AIModelConfig)
class AIModelConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "model", "temperature", "is_default", "updated_at")
    list_filter = ("tenant", "is_default")
    search_fields = ("name", "model")


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "user", "module", "status", "updated_at")
    list_filter = ("tenant", "module", "status")
    search_fields = ("title", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at", "prompt_tokens", "completion_tokens")
    list_filter = ("role", "tenant")
    search_fields = ("content", "tool_name")
    readonly_fields = ("created_at",)


@admin.register(AIAction)
class AIActionAdmin(admin.ModelAdmin):
    list_display = (
        "title", "tenant", "action_type", "status",
        "risk_level", "proposed_by", "approved_by", "created_at",
    )
    list_filter = ("tenant", "status", "risk_level", "action_type")
    search_fields = ("title", "summary", "action_type")
    readonly_fields = ("created_at", "updated_at", "executed_at")


@admin.register(AIToolCall)
class AIToolCallAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "tenant", "status", "duration_ms", "created_at")
    list_filter = ("tenant", "status", "tool_name")
    readonly_fields = ("created_at",)


@admin.register(AIPromptTemplate)
class AIPromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "module", "version", "is_active", "updated_at")
    list_filter = ("tenant", "module", "is_active")
    search_fields = ("name", "title")


@admin.register(AIAuditLog)
class AIAuditLogAdmin(admin.ModelAdmin):
    list_display = ("event", "tenant", "actor", "target_model", "created_at")
    list_filter = ("tenant", "event")
    search_fields = ("target_id", "target_model")
    readonly_fields = ("created_at",)
