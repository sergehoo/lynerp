"""
Endpoints API directs pour la recherche web (raccourcis UI / curl).

- ``POST /api/ai/web/search/``    body: {query, locale?, limit?, provider?}
- ``POST /api/ai/web/fetch/``     body: {url, max_chars?}
- ``POST /api/ai/web/research/``  body: {question, locale?, pages?}
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.permissions import CanUseAI
from ai_assistant.services.tool_registry import get_tool_registry
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
        result = tool.handler(
            tenant=tenant,
            user=request.user,
            conversation=None,
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Web tool %s failed", name)
        return Response(
            {"detail": str(exc)[:500], "code": "tool_failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response({"tool": name, "result": result})


class WebSearchView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        q = (request.data.get("query") or "").strip()
        if not q:
            return Response(
                {"detail": "query requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "web.search", request,
            query=q,
            locale=request.data.get("locale", "fr-fr"),
            limit=int(request.data.get("limit", 8)),
            provider=request.data.get("provider"),
        )


class WebFetchView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        url = (request.data.get("url") or "").strip()
        if not url:
            return Response(
                {"detail": "url requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "web.fetch", request,
            url=url,
            max_chars=int(request.data.get("max_chars", 8000)),
        )


class WebResearchView(APIView):
    permission_classes = [IsAuthenticated, CanUseAI]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response(
                {"detail": "question requis.", "code": "missing_param"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _run_tool(
            "web.research", request,
            question=question,
            locale=request.data.get("locale", "fr-fr"),
            pages=int(request.data.get("pages", 3)),
            max_chars_per_page=int(request.data.get("max_chars_per_page", 3500)),
            provider=request.data.get("provider"),
        )
