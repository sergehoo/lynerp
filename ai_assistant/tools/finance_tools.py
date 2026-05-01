"""
Outils IA pour le module Finance / Comptabilité.

- Lecture : analyse balance, détection d'anomalies sur transactions.
- Écriture : suggestion d'écriture comptable → produite en mode AIAction
  (PROPOSED), JAMAIS écrite directement en base.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.prompt_registry import get_prompt_registry
from ai_assistant.services.tool_registry import (
    RISK_READ,
    RISK_WRITE,
    get_tool_registry,
)

logger = logging.getLogger(__name__)
registry = get_tool_registry()


# --------------------------------------------------------------------------- #
# Lecture : analyse balance
# --------------------------------------------------------------------------- #
@registry.tool(
    name="finance.analyze_balance",
    description="Analyse la balance comptable d'une période et fournit un rapport.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "period_id": {"type": "string"},
        },
        "required": ["period_id"],
        "additionalProperties": False,
    },
    module="finance",
)
def analyze_balance(*, tenant, user, period_id: str, **_) -> Dict[str, Any]:
    from django.db.models import Sum
    from finance.models import AccountingPeriod, JournalLine

    period = AccountingPeriod.objects.filter(
        tenant=tenant, id=period_id,
    ).first()
    if period is None:
        return {"error": "period_not_found"}

    rows = list(
        JournalLine.objects
        .filter(
            tenant=tenant,
            entry__period=period,
            entry__status="POSTED",
        )
        .values("account__code", "account__name", "account__type")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        .order_by("account__code")
    )

    balance_payload = [
        {
            "code": r["account__code"],
            "name": r["account__name"],
            "type": r["account__type"],
            "debit": float(r["total_debit"] or 0),
            "credit": float(r["total_credit"] or 0),
            "balance": float((r["total_debit"] or 0) - (r["total_credit"] or 0)),
        }
        for r in rows
    ]

    prompt = get_prompt_registry().render(
        "finance.balance_analysis",
        context={
            "balance_json": str(balance_payload)[:12000],
            "period_label": period.name,
            "currency": getattr(tenant, "currency", "XOF"),
        },
        tenant=tenant,
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un expert-comptable senior."},
        {"role": "user", "content": prompt},
    ])
    return {
        "report_markdown": result.get("content", ""),
        "balance": balance_payload,
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }


@registry.tool(
    name="finance.detect_anomalies",
    description="Détecte les anomalies dans les écritures comptables récentes.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 30},
            "limit": {"type": "integer", "minimum": 10, "maximum": 500, "default": 100},
        },
        "additionalProperties": False,
    },
    module="finance",
)
def detect_anomalies(
    *,
    tenant,
    user,
    days: int = 30,
    limit: int = 100,
    **_,
) -> Dict[str, Any]:
    from finance.models import JournalLine

    since = date.today() - timedelta(days=days)
    rows = list(
        JournalLine.objects
        .filter(
            tenant=tenant,
            entry__entry_date__gte=since,
            entry__status="POSTED",
        )
        .select_related("account", "entry")
        .order_by("-entry__entry_date")[:limit]
    )

    transactions = [
        {
            "id": str(line.id),
            "date": line.entry.entry_date.isoformat() if line.entry.entry_date else None,
            "label": line.label or line.entry.label,
            "account": f"{line.account.code} - {line.account.name}",
            "debit": float(line.debit or 0),
            "credit": float(line.credit or 0),
            "currency": line.currency,
        }
        for line in rows
    ]

    prompt = get_prompt_registry().render(
        "finance.anomaly_detection",
        context={"transactions_json": str(transactions)[:12000]},
        tenant=tenant,
    )
    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un auditeur financier expérimenté."},
        {"role": "user", "content": prompt},
    ])
    return {
        "data": result.get("data") or {},
        "scanned_count": len(transactions),
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }


# --------------------------------------------------------------------------- #
# Écriture : suggestion d'écriture comptable (mode AIAction)
# --------------------------------------------------------------------------- #
@registry.tool(
    name="finance.suggest_journal_entry",
    description=(
        "Propose une écriture comptable pour une transaction. "
        "Crée une AIAction PROPOSED (validation humaine requise)."
    ),
    risk=RISK_WRITE,
    schema={
        "type": "object",
        "properties": {
            "transaction_description": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string"},
            "transaction_date": {"type": "string", "format": "date"},
        },
        "required": ["transaction_description", "amount"],
        "additionalProperties": False,
    },
    module="finance",
)
def suggest_journal_entry(
    *,
    tenant,
    user,
    conversation,
    transaction_description: str,
    amount: float,
    currency: str = "",
    transaction_date: str = "",
    **_,
) -> Dict[str, Any]:
    """
    Cet outil ne crée pas de JournalEntry directement : il propose une
    AIAction qui devra être approuvée par un comptable.
    """
    from ai_assistant.models import AIAction
    from finance.models import Account, CompanyFinanceProfile

    profile = CompanyFinanceProfile.objects.filter(tenant=tenant).first()
    standard = profile.standard if profile else "SYSCOHADA"
    currency = currency or (profile.base_currency if profile else "XOF")

    # On donne au LLM un extrait limité du plan comptable pour qu'il ait
    # de quoi raisonner sans saturer le contexte.
    accounts = list(
        Account.objects.filter(tenant=tenant, is_active=True)
        .order_by("code")
        .values("code", "name", "type")[:200]
    )

    prompt = get_prompt_registry().render(
        "finance.journal_entry_suggestion",
        context={
            "transaction_description": transaction_description[:2000],
            "amount": f"{Decimal(str(amount)):.2f}",
            "currency": currency,
            "transaction_date": transaction_date or date.today().isoformat(),
            "accounting_standard": standard,
            "accounts_extract": str(accounts)[:6000],
        },
        tenant=tenant,
    )
    result = get_ollama().chat_json([
        {"role": "system", "content": "Tu es un expert-comptable certifié."},
        {"role": "user", "content": prompt},
    ])
    suggestion = result.get("data") or {}

    # Crée une AIAction PROPOSED — l'humain validera.
    action = AIAction.objects.create(
        tenant=tenant,
        conversation=conversation,
        proposed_by=user if (user and user.is_authenticated) else None,
        action_type="finance.post_journal_entry",
        title=f"Proposition d'écriture : {transaction_description[:60]}",
        summary=suggestion.get("rationale", "")[:1000],
        payload={
            "label": suggestion.get("label", "")[:255],
            "lines": suggestion.get("lines", []),
            "currency": currency,
            "amount": float(amount),
            "transaction_date": transaction_date or date.today().isoformat(),
        },
        risk_level="MEDIUM",
        requires_double_approval=False,
    )

    return {
        "action_id": str(action.id),
        "status": action.status,
        "suggestion": suggestion,
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
        "_message": (
            "Écriture suggérée — création soumise à validation humaine. "
            f"Voir AIAction {action.id}."
        ),
    }
