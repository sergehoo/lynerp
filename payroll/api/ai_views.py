"""Endpoints IA pour la paie (explication bulletin, anomalies, simulation)."""
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
        logger.exception("Payroll AI tool %s failed", name)
        return Response(
            {"detail": str(exc)[:500], "code": "tool_failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    log_event(
        tenant=tenant, actor=request.user,
        event=AIAuditEvent.TOOL_CALLED,
        target_model=f"payroll.AIShortcut.{name}",
        payload={"tool": name},
        request=request,
    )
    return Response({"tool": name, "result": result})


class ExplainPayslipView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        slip_id = request.data.get("payslip_id")
        if not slip_id:
            return Response(
                {"detail": "payslip_id requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool("payroll.explain_payslip", request, payslip_id=slip_id)


class DetectPayrollAnomaliesView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        period_id = request.data.get("period_id")
        if not period_id:
            return Response(
                {"detail": "period_id requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool("payroll.detect_anomalies", request, period_id=period_id)


class SimulateSalaryView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        profile_id = request.data.get("profile_id")
        base = request.data.get("base_salary")
        if not profile_id or base is None:
            return Response(
                {"detail": "profile_id et base_salary requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "payroll.simulate_salary", request,
            profile_id=profile_id,
            base_salary=float(base),
            currency=request.data.get("currency", "XOF"),
        )
