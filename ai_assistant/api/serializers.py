from __future__ import annotations

from rest_framework import serializers

from ai_assistant.models import (
    AIAction,
    AIActionStatus,
    AIConversation,
    AIMessage,
    AIToolCall,
)


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = [
            "id", "role", "content",
            "tool_name", "tool_arguments", "tool_result",
            "prompt_tokens", "completion_tokens",
            "metadata", "created_at",
        ]
        read_only_fields = fields


class AIConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AIConversation
        fields = [
            "id", "title", "module", "status",
            "metadata", "message_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "message_count", "created_at", "updated_at"]


class AIConversationDetailSerializer(AIConversationSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta(AIConversationSerializer.Meta):
        fields = AIConversationSerializer.Meta.fields + ["messages"]


class AIToolCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIToolCall
        fields = [
            "id", "tool_name", "arguments", "result",
            "status", "duration_ms", "error_message", "created_at",
        ]
        read_only_fields = fields


class AIActionSerializer(serializers.ModelSerializer):
    is_pending = serializers.BooleanField(read_only=True)
    is_actionable = serializers.BooleanField(read_only=True)

    class Meta:
        model = AIAction
        fields = [
            "id", "conversation", "action_type", "title", "summary",
            "payload", "risk_level", "status",
            "requires_double_approval",
            "proposed_by", "approved_by", "second_approved_by",
            "rejected_by", "rejection_reason",
            "executed_at", "execution_result", "error_message",
            "expires_at", "is_pending", "is_actionable",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "proposed_by", "approved_by", "second_approved_by",
            "rejected_by", "executed_at", "execution_result", "error_message",
            "is_pending", "is_actionable", "created_at", "updated_at",
        ]


class SendMessageRequestSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=10000)
    stream = serializers.BooleanField(default=False)


class CreateConversationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    module = serializers.ChoiceField(
        choices=[
            ("general", "general"),
            ("hr", "hr"),
            ("finance", "finance"),
            ("payroll", "payroll"),
            ("logistics", "logistics"),
            ("admin", "admin"),
        ],
        default="general",
    )


class ApproveActionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class RejectActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, max_length=1000)
