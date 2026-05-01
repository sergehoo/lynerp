"""
API DRF du module IA.

- ``GET/POST /api/ai/conversations/``      : liste / création
- ``GET/DELETE /api/ai/conversations/<id>/`` : détail / suppression logique
- ``POST /api/ai/conversations/<id>/messages/`` : envoi d'un message (+stream)
- ``GET/POST /api/ai/actions/``            : liste actions / création (rare)
- ``POST /api/ai/actions/<id>/approve/``   : valider
- ``POST /api/ai/actions/<id>/reject/``    : rejeter
- ``POST /api/ai/actions/<id>/execute/``   : exécuter l'action approuvée
- ``POST /api/ai/tools/<name>/run/``       : exécuter un outil read-only directement
"""
from __future__ import annotations

import json
import logging

from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.api.serializers import (
    AIActionSerializer,
    AIConversationDetailSerializer,
    AIConversationSerializer,
    AIMessageSerializer,
    ApproveActionSerializer,
    CreateConversationSerializer,
    RejectActionSerializer,
    SendMessageRequestSerializer,
)
from ai_assistant.models import (
    AIAction,
    AIActionStatus,
    AIAuditEvent,
    AIConversation,
    AIConversationStatus,
    AIMessage,
    AIMessageRole,
)
from ai_assistant.permissions import CanApproveAIAction, CanUseAI
from ai_assistant.services.audit import log_event
from ai_assistant.services.runner import ConversationRunner
from ai_assistant.services.tool_registry import get_tool_registry, RISK_DESTRUCTIVE
from Lyneerp.core.permissions import _request_tenant

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Conversations
# --------------------------------------------------------------------------- #
class AIConversationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanUseAI]

    def get_queryset(self):
        tenant = _request_tenant(self.request)
        if tenant is None:
            return AIConversation.objects.none()
        return (
            AIConversation.objects
            .filter(tenant=tenant, user=self.request.user)
            .exclude(status=AIConversationStatus.DELETED)
            .annotate()
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AIConversationDetailSerializer
        return AIConversationSerializer

    def create(self, request, *args, **kwargs):
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = _request_tenant(request)
        conv = AIConversation.objects.create(
            tenant=tenant,
            user=request.user,
            title=serializer.validated_data.get("title", ""),
            module=serializer.validated_data.get("module", "general"),
        )
        out = AIConversationSerializer(conv).data
        return Response(out, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: AIConversation) -> None:
        instance.status = AIConversationStatus.DELETED
        instance.save(update_fields=["status", "updated_at"])

    # ------------------------------------------------------------------ #
    # Envoi d'un message
    # ------------------------------------------------------------------ #
    @action(detail=True, methods=["post"], url_path="messages")
    def send_message(self, request, pk=None):
        conv = self.get_object()
        body = SendMessageRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        content = body.validated_data["content"]
        do_stream = body.validated_data["stream"]

        runner = ConversationRunner(conv)

        if do_stream:
            generator = runner.send_user_message(
                content, request=request, stream=True,
            )

            def sse():
                # Server-Sent Events : `data: <json>\n\n`
                for evt in generator:
                    payload = json.dumps(evt, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

            response = StreamingHttpResponse(
                sse(), content_type="text/event-stream",
            )
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            return response

        assistant_msg = runner.send_user_message(content, request=request)
        return Response(
            AIMessageSerializer(assistant_msg).data,
            status=status.HTTP_201_CREATED,
        )


# --------------------------------------------------------------------------- #
# Actions IA (validation humaine)
# --------------------------------------------------------------------------- #
class AIActionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, CanUseAI]
    serializer_class = AIActionSerializer

    def get_queryset(self):
        tenant = _request_tenant(self.request)
        if tenant is None:
            return AIAction.objects.none()
        return AIAction.objects.filter(tenant=tenant).order_by("-created_at")

    @action(
        detail=True, methods=["post"], url_path="approve",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def approve(self, request, pk=None):
        ai_action: AIAction = self.get_object()
        if ai_action.status != AIActionStatus.PROPOSED:
            return Response(
                {"detail": "Action déjà traitée.", "code": "invalid_status"},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            now = timezone.now()
            if ai_action.requires_double_approval and ai_action.approved_by_id:
                # Seconde approbation
                if ai_action.approved_by_id == request.user.id:
                    return Response(
                        {"detail": "Deuxième approbateur différent requis.", "code": "same_approver"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                ai_action.second_approved_by = request.user
                ai_action.second_approved_at = now
            else:
                ai_action.approved_by = request.user
                ai_action.approved_at = now

            if ai_action.is_actionable:
                ai_action.status = AIActionStatus.APPROVED
            ai_action.save()

        log_event(
            tenant=ai_action.tenant, actor=request.user,
            conversation=ai_action.conversation,
            event=AIAuditEvent.ACTION_APPROVED,
            target_model="ai_assistant.AIAction",
            target_id=str(ai_action.id),
            payload={"action_type": ai_action.action_type},
            request=request,
        )
        return Response(AIActionSerializer(ai_action).data)

    @action(
        detail=True, methods=["post"], url_path="reject",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def reject(self, request, pk=None):
        ai_action: AIAction = self.get_object()
        if ai_action.status not in {AIActionStatus.PROPOSED, AIActionStatus.APPROVED}:
            return Response(
                {"detail": "Action déjà traitée.", "code": "invalid_status"},
                status=status.HTTP_409_CONFLICT,
            )
        body = RejectActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        ai_action.status = AIActionStatus.REJECTED
        ai_action.rejected_by = request.user
        ai_action.rejected_at = timezone.now()
        ai_action.rejection_reason = body.validated_data["reason"]
        ai_action.save()

        log_event(
            tenant=ai_action.tenant, actor=request.user,
            conversation=ai_action.conversation,
            event=AIAuditEvent.ACTION_REJECTED,
            target_model="ai_assistant.AIAction",
            target_id=str(ai_action.id),
            payload={"reason": ai_action.rejection_reason[:500]},
            request=request,
        )
        return Response(AIActionSerializer(ai_action).data)

    @action(
        detail=True, methods=["post"], url_path="execute",
        permission_classes=[IsAuthenticated, CanApproveAIAction],
    )
    def execute(self, request, pk=None):
        """
        Exécute l'action approuvée. La logique métier est déléguée à un
        registre d'``executors``.
        """
        ai_action: AIAction = self.get_object()
        if not ai_action.is_actionable:
            return Response(
                {"detail": "Action non exécutable.", "code": "not_actionable"},
                status=status.HTTP_409_CONFLICT,
            )

        from ai_assistant.executors import get_executor

        executor = get_executor(ai_action.action_type)
        if executor is None:
            return Response(
                {"detail": f"Aucun executor pour '{ai_action.action_type}'.",
                 "code": "no_executor"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                result = executor(ai_action=ai_action, user=request.user)
                ai_action.status = AIActionStatus.EXECUTED
                ai_action.executed_at = timezone.now()
                ai_action.execution_result = result or {}
                ai_action.save()
            log_event(
                tenant=ai_action.tenant, actor=request.user,
                conversation=ai_action.conversation,
                event=AIAuditEvent.ACTION_EXECUTED,
                target_model="ai_assistant.AIAction",
                target_id=str(ai_action.id),
                payload={"action_type": ai_action.action_type},
                request=request,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("AIAction executor failed for %s", ai_action.id)
            ai_action.status = AIActionStatus.FAILED
            ai_action.error_message = str(exc)[:1000]
            ai_action.save(update_fields=["status", "error_message", "updated_at"])
            log_event(
                tenant=ai_action.tenant, actor=request.user,
                conversation=ai_action.conversation,
                event=AIAuditEvent.ACTION_FAILED,
                target_model="ai_assistant.AIAction",
                target_id=str(ai_action.id),
                payload={"error": str(exc)[:500]},
                request=request,
            )
            return Response(
                AIActionSerializer(ai_action).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(AIActionSerializer(ai_action).data)


# --------------------------------------------------------------------------- #
# Tools : exécution directe d'un outil read (boutons "Analyser", "Suggérer"…)
# --------------------------------------------------------------------------- #
from rest_framework.views import APIView


class ToolRunView(APIView):
    """POST /api/ai/tools/<name>/run/  body: arguments JSON."""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request, name: str):
        tool = get_tool_registry().get(name)
        if tool is None:
            return Response(
                {"detail": f"Outil '{name}' inconnu.", "code": "unknown_tool"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if tool.risk == RISK_DESTRUCTIVE:
            return Response(
                {"detail": "Outils destructifs interdits via cet endpoint.",
                 "code": "destructive_blocked"},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant = _request_tenant(request)
        # Conversation optionnelle (pour AIAction)
        conv_id = request.data.get("conversation_id")
        conv = None
        if conv_id:
            conv = AIConversation.objects.filter(
                tenant=tenant, user=request.user, id=conv_id,
            ).first()

        try:
            result = tool.handler(
                tenant=tenant,
                user=request.user,
                conversation=conv,
                **{k: v for k, v in request.data.items()
                   if k not in {"conversation_id"}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s failed", name)
            return Response(
                {"detail": str(exc)[:500], "code": "tool_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log_event(
            tenant=tenant, actor=request.user,
            conversation=conv,
            event=AIAuditEvent.TOOL_CALLED,
            target_model="ai_assistant.AIToolCall",
            target_id=name,
            payload={"tool": name, "risk": tool.risk},
            request=request,
        )
        return Response({"tool": name, "risk": tool.risk, "result": result})
