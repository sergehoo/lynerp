"""Outils IA pour le module CRM."""
from __future__ import annotations

import logging
from typing import Any, Dict

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="crm.score_lead",
    description=(
        "Score un lead (0-100) en fonction de son profil. Met à jour ai_score "
        "et ai_score_explanation sur le Lead. Lecture/écriture limitée au "
        "lead lui-même."
    ),
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"lead_id": {"type": "string"}},
        "required": ["lead_id"],
        "additionalProperties": False,
    },
    module="crm",
)
def score_lead(*, tenant, user, lead_id: str, **_) -> Dict[str, Any]:
    from crm.models import Lead

    lead = Lead.objects.filter(tenant=tenant, id=lead_id).first()
    if lead is None:
        return {"error": "lead_not_found"}

    payload = {
        "company": lead.company,
        "industry": lead.industry,
        "source": lead.source,
        "email_provided": bool(lead.email),
        "phone_provided": bool(lead.phone),
        "notes": (lead.notes or "")[:600],
    }
    user_msg = (
        "Tu es un commercial expert. Score ce lead de 0 à 100 et donne 1-2 "
        "phrases d'explication. Réponds en JSON strict :\n"
        '{"score": 0-100, "rationale": "...", "next_action": "..."}\n\n'
        f"Lead :\n{payload}"
    )
    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un consultant commercial."},
        {"role": "user", "content": user_msg},
    ])
    data = result.get("data") or {}
    score = max(0, min(100, int(data.get("score", 0))))

    lead.ai_score = score
    lead.ai_score_explanation = (data.get("rationale", "")[:1000])
    lead.save(update_fields=["ai_score", "ai_score_explanation", "updated_at"])

    return {
        "lead_id": lead_id,
        "score": score,
        "rationale": data.get("rationale", ""),
        "next_action": data.get("next_action", ""),
        "model": result.get("model"),
    }


@registry.tool(
    name="crm.next_best_actions",
    description="Suggère les prochaines actions sur les opportunités ouvertes.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}},
        "additionalProperties": False,
    },
    module="crm",
)
def next_best_actions(*, tenant, user, limit: int = 5, **_) -> Dict[str, Any]:
    from datetime import date, timedelta

    from crm.models import Opportunity, OpportunityStatus

    soon = date.today() + timedelta(days=14)
    opps = list(
        Opportunity.objects
        .filter(
            tenant=tenant, status=OpportunityStatus.OPEN,
            expected_close_date__lte=soon,
        )
        .select_related("account", "stage")
        .order_by("expected_close_date")[:limit]
    )
    if not opps:
        return {"actions": [], "summary": "Aucune opportunité à clôturer dans les 14 jours."}

    payload = [
        {
            "name": o.name, "account": o.account.name,
            "amount": float(o.amount), "stage": o.stage.name,
            "probability": float(o.win_probability),
            "expected_close": o.expected_close_date.isoformat() if o.expected_close_date else None,
        }
        for o in opps
    ]
    msg = (
        "Voici les opportunités à clôturer dans les 14 jours. "
        "Suggère pour chacune l'action commerciale la plus utile (Markdown).\n\n"
        f"{payload}"
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un directeur commercial pragmatique."},
        {"role": "user", "content": msg},
    ])
    return {
        "actions_markdown": result.get("content", ""),
        "opportunities": payload,
        "model": result.get("model"),
    }
