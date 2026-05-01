"""
Endpoints DRF d'intégration IA pour le module Finance / Comptabilité.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.permissions import CanUseAI
from ai_assistant.services.audit import log_event
from ai_assistant.services.tool_registry import get_tool_registry
from ai_assistant.models import AIAuditEvent
from Lyneerp.core.permissions import _request_tenant

logger = logging.getLogger(__name__)


def _run_tool(name: str, request, **kwargs):
    tool = get_tool_registry().get(name)
    if tool is None:
        return Response(
            {"detail": f"Outil '{name}' indisponible.", "code": "tool_missing"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    tenant = _request_tenant(request)
    try:
        result = tool.handler(tenant=tenant, user=request.user, conversation=None, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI tool %s failed", name)
        return Response(
            {"detail": str(exc)[:500], "code": "tool_failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    log_event(
        tenant=tenant, actor=request.user,
        event=AIAuditEvent.TOOL_CALLED,
        target_model=f"finance.AIShortcut.{name}",
        target_id="",
        payload={"args": list(kwargs.keys())},
        request=request,
    )
    return Response({"tool": name, "result": result})


class AnalyzeBalanceView(APIView):
    """POST /api/finance/ai/analyze-balance/  body: {period_id}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        period_id = request.data.get("period_id")
        if not period_id:
            return Response(
                {"detail": "period_id requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool("finance.analyze_balance", request, period_id=period_id)


class DetectAnomaliesView(APIView):
    """POST /api/finance/ai/detect-anomalies/  body: {days?, limit?}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        return _run_tool(
            "finance.detect_anomalies", request,
            days=int(request.data.get("days", 30)),
            limit=int(request.data.get("limit", 100)),
        )


class SuggestJournalEntryView(APIView):
    """POST /api/finance/ai/suggest-journal-entry/  body: {transaction_description, amount, currency?, transaction_date?}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        desc = request.data.get("transaction_description")
        amount = request.data.get("amount")
        if not desc or amount is None:
            return Response(
                {"detail": "transaction_description et amount requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "finance.suggest_journal_entry", request,
            transaction_description=desc,
            amount=float(amount),
            currency=request.data.get("currency", ""),
            transaction_date=request.data.get("transaction_date", ""),
        )
