"""
Outils IA web : recherche, fetch URL, recherche profonde (RAG live).

Tous lecture seule : aucune modification de DB métier.
Garde-fous : SSRF, allowlist/blocklist, rate-limit, audit.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ai_assistant.services.web.fetch import WebFetchError, web_fetch
from ai_assistant.services.web.research import deep_research
from ai_assistant.services.web.search import WebSearchError, web_search
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="web.search",
    description=(
        "Recherche sur le web (DuckDuckGo / Brave / SearxNG selon la "
        "configuration). Renvoie les liens pertinents avec titre + extrait."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "locale": {"type": "string", "default": "fr-fr"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 15, "default": 8},
            "provider": {
                "type": "string",
                "enum": ["ddg", "brave", "searx"],
                "description": "Override du provider par défaut.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    module="web",
)
def search(
    *,
    tenant,
    user,
    query: str,
    locale: str = "fr-fr",
    limit: int = 8,
    provider: str | None = None,
    **_,
) -> Dict[str, Any]:
    tenant_id = str(tenant.id) if tenant is not None else None
    try:
        out = web_search(
            query=query, locale=locale, limit=limit,
            provider=provider, tenant_id=tenant_id,
        )
    except WebSearchError as exc:
        return {"error": str(exc)}

    _audit(tenant=tenant, user=user, action="search",
           target=query[:200], success=True,
           details={"results": len(out.get("results", [])),
                    "provider": out.get("provider")})
    return {
        "query": out["query"],
        "provider": out["provider"],
        "results": out["results"],
        "cached": out["cached"],
        "duration_ms": out.get("duration_ms"),
    }


@registry.tool(
    name="web.fetch",
    description=(
        "Récupère le contenu textuel d'une URL publique (HTML / texte). "
        "Refuse les URL internes (SSRF), les binaires et les domaines en "
        "blocklist."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "minimum": 500, "maximum": 50000, "default": 8000},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    module="web",
)
def fetch(*, tenant, user, url: str, max_chars: int = 8000, **_) -> Dict[str, Any]:
    tenant_id = str(tenant.id) if tenant is not None else None
    try:
        out = web_fetch(url, tenant_id=tenant_id, max_chars=max_chars)
    except WebFetchError as exc:
        _audit(tenant=tenant, user=user, action="fetch", target=url[:200],
               success=False, details={"error": str(exc)})
        return {"error": str(exc)}

    _audit(tenant=tenant, user=user, action="fetch", target=url[:200],
           success=True, details={"chars": out.get("char_count"), "cached": out.get("cached")})
    return out


@registry.tool(
    name="web.research",
    description=(
        "Recherche profonde : combine search + fetch des N meilleurs résultats + "
        "synthèse Markdown avec citations [1][2]…. Idéal quand LyneAI ne "
        "dispose pas localement de l'information."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "locale": {"type": "string", "default": "fr-fr"},
            "pages": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3},
            "max_chars_per_page": {"type": "integer", "minimum": 1000, "maximum": 8000, "default": 3500},
            "provider": {"type": "string", "enum": ["ddg", "brave", "searx"]},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
    module="web",
)
def research(
    *,
    tenant,
    user,
    question: str,
    locale: str = "fr-fr",
    pages: int = 3,
    max_chars_per_page: int = 3500,
    provider: str | None = None,
    **_,
) -> Dict[str, Any]:
    out = deep_research(
        question=question,
        tenant=tenant,
        locale=locale,
        pages=pages,
        max_chars_per_page=max_chars_per_page,
        provider=provider,
    )
    _audit(tenant=tenant, user=user, action="research",
           target=question[:200],
           success=not bool(out.get("error")),
           details={
               "sources": len(out.get("sources", [])),
               "provider": out.get("provider"),
               "model": out.get("model"),
           })
    return out


# --------------------------------------------------------------------------- #
# Audit interne (utilise WebFetchAudit si disponible)
# --------------------------------------------------------------------------- #
def _audit(*, tenant, user, action: str, target: str, success: bool, details: Dict[str, Any] | None = None) -> None:
    try:
        from ai_assistant.models import WebFetchAudit

        WebFetchAudit.objects.create(
            tenant=tenant,
            actor=user if (user and getattr(user, "is_authenticated", False)) else None,
            action=action,
            target=target[:500],
            success=success,
            details=details or {},
        )
    except Exception:  # noqa: BLE001
        # WebFetchAudit n'existe peut-être pas encore (fresh install) : silent.
        logger.debug("WebFetchAudit unavailable", exc_info=False)
