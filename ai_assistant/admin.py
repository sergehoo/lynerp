from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, F, Sum
from django.urls import reverse
from django.utils.html import format_html

from ai_assistant.models import (
    AIAction,
    AIAuditLog,
    AIConversation,
    AIMessage,
    AIModelConfig,
    AIPromptTemplate,
    AIToolCall,
    OHADAArticle,
    OHADANote,
    WebFetchAudit,
)


@admin.register(AIModelConfig)
class AIModelConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "model", "temperature", "is_default", "updated_at")
    list_filter = ("tenant", "is_default")
    search_fields = ("name", "model")


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = (
        "title", "tenant", "user", "module", "status",
        "messages_count", "tokens_total", "tokens_prompt", "tokens_completion",
        "updated_at",
    )
    list_filter = ("tenant", "module", "status")
    search_fields = ("title", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        """Annotate token totals once for the listing page."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _msg_count=Count("messages"),
            _tok_prompt=Sum("messages__prompt_tokens"),
            _tok_completion=Sum("messages__completion_tokens"),
        )

    @admin.display(ordering="_msg_count", description="Msg")
    def messages_count(self, obj):
        return obj._msg_count or 0

    @admin.display(ordering="_tok_prompt", description="Prompt tk")
    def tokens_prompt(self, obj):
        return obj._tok_prompt or 0

    @admin.display(ordering="_tok_completion", description="Compl. tk")
    def tokens_completion(self, obj):
        return obj._tok_completion or 0

    @admin.display(description="Tokens")
    def tokens_total(self, obj):
        total = (obj._tok_prompt or 0) + (obj._tok_completion or 0)
        return format_html("<strong>{}</strong>", total)


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = (
        "conversation", "role", "tokens_total",
        "prompt_tokens", "completion_tokens", "created_at",
    )
    list_filter = ("role", "tenant", "conversation__module")
    search_fields = ("content", "tool_name", "conversation__title")
    readonly_fields = ("created_at",)
    list_select_related = ("conversation",)

    @admin.display(description="Total tk")
    def tokens_total(self, obj):
        total = int(obj.prompt_tokens or 0) + int(obj.completion_tokens or 0)
        return format_html("<strong>{}</strong>", total)


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


@admin.register(WebFetchAudit)
class WebFetchAuditAdmin(admin.ModelAdmin):
    list_display = ("action", "tenant", "actor", "success", "target", "created_at")
    list_filter = ("tenant", "action", "success")
    search_fields = ("target",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(OHADAArticle)
class OHADAArticleAdmin(admin.ModelAdmin):
    list_display = ("reference", "acte", "title", "version", "is_active", "updated_at")
    list_filter = ("acte", "is_active")
    search_fields = ("reference", "title", "summary")


@admin.register(OHADANote)
class OHADANoteAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "article", "author", "updated_at")
    list_filter = ("tenant",)
    search_fields = ("title", "content")
