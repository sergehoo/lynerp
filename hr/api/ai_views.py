"""
Endpoints DRF d'intégration IA pour le module RH.

Ces vues sont des raccourcis "frontaux" : elles appellent les outils
``hr_tools`` via le registre, en s'assurant que la requête est faite par un
utilisateur du tenant courant. Elles sont pratiques pour les boutons
"Analyser CV", "Générer questions", "Comparer candidats" dans l'UI RH.
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
        target_model=f"hr.AIShortcut.{name}",
        target_id="",
        payload={"args": list(kwargs.keys())},
        request=request,
    )
    return Response({"tool": name, "result": result})


class AnalyzeResumeView(APIView):
    """POST /api/rh/ai/analyze-resume/  body: {application_id} ou {resume_text}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        application_id = request.data.get("application_id")
        resume_text = request.data.get("resume_text")
        return _run_tool(
            "hr.analyze_resume", request,
            application_id=application_id,
            resume_text=resume_text,
        )


class GenerateInterviewQuestionsView(APIView):
    """POST /api/rh/ai/interview-questions/  body: {recruitment_id, candidate_summary?}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        recruitment_id = request.data.get("recruitment_id")
        if not recruitment_id:
            return Response(
                {"detail": "recruitment_id requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "hr.generate_interview_questions", request,
            recruitment_id=recruitment_id,
            candidate_summary=request.data.get("candidate_summary", ""),
        )


class SummarizeContractView(APIView):
    """POST /api/rh/ai/summarize-contract/  body: {contract_id} ou {contract_text}"""

    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        return _run_tool(
            "hr.summarize_contract", request,
            contract_id=request.data.get("contract_id"),
            contract_text=request.data.get("contract_text"),
        )
