"""Endpoints IA stock."""
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
        logger.exception("Inventory AI tool %s failed", name)
        return Response(
            {"detail": str(exc)[:500], "code": "tool_failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    log_event(
        tenant=tenant, actor=request.user,
        event=AIAuditEvent.TOOL_CALLED,
        target_model=f"inventory.AIShortcut.{name}",
        payload={"tool": name},
        request=request,
    )
    return Response({"tool": name, "result": result})


class ForecastStockoutsView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        return _run_tool(
            "inventory.forecast_stockouts", request,
            horizon_days=int(request.data.get("horizon_days", 14)),
            history_days=int(request.data.get("history_days", 30)),
        )


class RecommendReorderView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        warehouse_id = request.data.get("warehouse_id")
        if not warehouse_id:
            return Response(
                {"detail": "warehouse_id requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "inventory.recommend_reorder", request,
            warehouse_id=warehouse_id,
            supplier_id=request.data.get("supplier_id"),
        )


class AnalyzeSuppliersView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        return _run_tool("inventory.analyze_suppliers", request)
