"""Outils IA pour l'administration / workflows."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from django.utils import timezone

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="admin.recent_activities",
    description="Résume les activités récentes (audit) du tenant courant.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "hours": {"type": "integer", "minimum": 1, "maximum": 168, "default": 24},
            "severity_min": {"type": "string", "default": "LOW"},
        },
        "additionalProperties": False,
    },
    module="admin",
)
def recent_activities(*, tenant, user, hours: int = 24, severity_min: str = "LOW", **_) -> Dict[str, Any]:
    try:
        from workflows.models import AuditEvent
    except Exception:  # noqa: BLE001
        return {"error": "workflows_app_unavailable"}

    severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    threshold = severity_order.get(severity_min.upper(), 0)
    since = timezone.now() - timedelta(hours=hours)
    events = list(
        AuditEvent.objects.filter(tenant=tenant, created_at__gte=since)
        .order_by("-created_at")[:200]
    )
    filtered = [
        {
            "event_type": e.event_type,
            "severity": e.severity,
            "actor": str(e.actor) if e.actor else "système",
            "target": f"{e.target_model}:{e.target_id}" if e.target_model else "",
            "description": (e.description or "")[:300],
            "at": e.created_at.isoformat(),
        }
        for e in events
        if severity_order.get(e.severity, 0) >= threshold
    ]

    if not filtered:
        return {"summary": "Aucune activité dans la fenêtre demandée.", "events": []}

    msg = (
        f"Voici les activités récentes ({hours}h) du tenant. "
        "Produis un résumé Markdown avec : faits saillants, risques, "
        "recommandations à prendre.\n\n"
        f"{filtered[:50]}"
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un superviseur ERP attentif aux risques."},
        {"role": "user", "content": msg},
    ])
    return {
        "summary_markdown": result.get("content", ""),
        "events": filtered,
        "model": result.get("model"),
    }


@registry.tool(
    name="admin.unusual_actions",
    description="Détecte les actions inhabituelles (créations multiples d'admins, etc.).",
    risk=RISK_READ,
    schema={"type": "object", "properties": {}, "additionalProperties": False},
    module="admin",
)
def unusual_actions(*, tenant, user, **_) -> Dict[str, Any]:
    try:
        from workflows.models import AuditEvent
    except Exception:  # noqa: BLE001
        return {"error": "workflows_app_unavailable"}

    flagged = []
    since = timezone.now() - timedelta(hours=24)
    high = AuditEvent.objects.filter(
        tenant=tenant, severity__in=["HIGH", "CRITICAL"], created_at__gte=since,
    ).order_by("-created_at")[:50]
    for ev in high:
        flagged.append({
            "event_type": ev.event_type,
            "severity": ev.severity,
            "actor": str(ev.actor) if ev.actor else "système",
            "at": ev.created_at.isoformat(),
            "description": (ev.description or "")[:300],
        })
    return {"count": len(flagged), "events": flagged}
