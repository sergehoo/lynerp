"""
Outils IA pour la connaissance OHADA.

- ``ohada.search``         : recherche full-text dans les Actes uniformes.
- ``ohada.cite``           : retourne un article par référence canonique.
- ``ohada.compliance_check``: vérification de conformité contextuelle (LLM).
- ``ohada.list_actes``     : liste des Actes uniformes disponibles.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ai_assistant.ohada.retrieval import (
    article_count,
    get_article,
    list_actes,
    search_ohada,
)
from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="ohada.search",
    description=(
        "Recherche dans la base de connaissances OHADA. Renvoie les "
        "articles pertinents (référence + résumé pivot) pour une "
        "question juridique ou comptable."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "actes": {
                "type": "array", "items": {"type": "string"},
                "description": "Filtrer sur des Actes (DCG, AUSCGIE, SURETES, ...)",
            },
            "modules": {
                "type": "array", "items": {"type": "string"},
                "description": "Filtrer sur des modules ERP (hr, finance, payroll, ...)",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 8},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    module="legal_ohada",
)
def search(
    *,
    tenant,
    user,
    query: str,
    actes: List[str] | None = None,
    modules: List[str] | None = None,
    limit: int = 8,
    **_,
) -> Dict[str, Any]:
    results = search_ohada(query=query, actes=actes, modules=modules, limit=limit)
    return {
        "query": query,
        "actes": actes or [],
        "modules": modules or [],
        "results": results,
        "count": len(results),
        "_disclaimer": (
            "Résumés-pivots à valeur informative. "
            "Consulter le texte officiel et un juriste OHADA agréé pour "
            "toute décision critique."
        ),
    }


@registry.tool(
    name="ohada.cite",
    description="Retourne un article OHADA par sa référence (ex. 'AUSCGIE-Art.4').",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"reference": {"type": "string"}},
        "required": ["reference"],
        "additionalProperties": False,
    },
    module="legal_ohada",
)
def cite(*, tenant, user, reference: str, **_) -> Dict[str, Any]:
    art = get_article(reference)
    if art is None:
        return {"error": "not_found", "reference": reference}
    return art


@registry.tool(
    name="ohada.list_actes",
    description="Liste les 10 Actes uniformes OHADA disponibles dans la base.",
    risk=RISK_READ,
    schema={"type": "object", "properties": {}, "additionalProperties": False},
    module="legal_ohada",
)
def list_acts(*, tenant, user, **_) -> Dict[str, Any]:
    return {
        "actes": list_actes(),
        "total_articles": article_count(),
    }


@registry.tool(
    name="ohada.compliance_check",
    description=(
        "Vérifie la conformité OHADA d'un texte ou d'une situation. "
        "Recherche les articles pertinents puis demande au LLM une analyse "
        "structurée. Réponse Markdown avec rappel obligatoire de validation "
        "juridique."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "context": {"type": "string"},
            "country": {"type": "string", "default": ""},
            "modules": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["context"],
        "additionalProperties": False,
    },
    module="legal_ohada",
)
def compliance_check(
    *,
    tenant,
    user,
    context: str,
    country: str = "",
    modules: List[str] | None = None,
    **_,
) -> Dict[str, Any]:
    from ai_assistant.services.prompt_registry import get_prompt_registry

    # Recherche d'articles pertinents avant le LLM (RAG simple).
    refs = search_ohada(query=context, modules=modules or None, limit=8)
    refs_text = "\n".join(
        f"- **{r['reference']}** — {r['title']} : {r['summary'][:300]}"
        for r in refs
    ) or "Aucun article trouvé dans la base — veuillez préciser le contexte."

    prompt = get_prompt_registry().render(
        "legal_ohada.compliance_summary",
        context={
            "context": context[:4000],
            "ohada_references": refs_text[:6000],
        },
        tenant=tenant,
    )
    result = get_ollama().chat([
        {"role": "system",
         "content": (
             "Tu es un juriste OHADA expert. Réponds en français, structuré, "
             "avec citations d'articles. Termine par l'avertissement légal."
         )},
        {"role": "user", "content": prompt},
    ])
    return {
        "country": country,
        "references_used": [r["reference"] for r in refs],
        "analysis_markdown": result.get("content", ""),
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
        "_disclaimer": (
            "Analyse informative — ne remplace pas la consultation d'un "
            "juriste OHADA agréé."
        ),
    }
