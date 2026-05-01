"""
Outils IA pour le module Paie.

Tous lecture seule : l'IA explique, analyse, simule. Aucun calcul réel
n'est délégué (le moteur déterministe ``payroll.services.engine`` reste
seule source de vérité).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List

from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.prompt_registry import get_prompt_registry
from ai_assistant.services.tool_registry import RISK_READ, get_tool_registry

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="payroll.explain_payslip",
    description="Explique un bulletin de paie de manière pédagogique.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"payslip_id": {"type": "string"}},
        "required": ["payslip_id"],
        "additionalProperties": False,
    },
    module="payroll",
)
def explain_payslip(*, tenant, user, payslip_id: str, **_) -> Dict[str, Any]:
    from payroll.models import Payslip

    slip = (
        Payslip.objects
        .filter(tenant=tenant, id=payslip_id)
        .select_related("employee", "period", "employee_profile")
        .prefetch_related("lines__item")
        .first()
    )
    if slip is None:
        return {"error": "payslip_not_found"}

    payload = _serialize_payslip_for_ai(slip)
    prompt = get_prompt_registry().render(
        "payroll.payslip_explanation",
        context={"payslip_json": str(payload)[:8000]},
        tenant=tenant,
    )
    result = get_ollama().chat([
        {"role": "system",
         "content": "Tu es un comptable de paie pédagogue. Explique sans jargon."},
        {"role": "user", "content": prompt},
    ])
    return {
        "explanation_markdown": result.get("content", ""),
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }


@registry.tool(
    name="payroll.detect_anomalies",
    description="Détecte les bulletins atypiques sur une période.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {"period_id": {"type": "string"}},
        "required": ["period_id"],
        "additionalProperties": False,
    },
    module="payroll",
)
def detect_payslip_anomalies(*, tenant, user, period_id: str, **_) -> Dict[str, Any]:
    from payroll.models import PayrollPeriod

    period = PayrollPeriod.objects.filter(tenant=tenant, id=period_id).first()
    if period is None:
        return {"error": "period_not_found"}

    slips = list(
        period.payslips.select_related("employee").only(
            "id", "slip_number", "gross_amount", "net_amount",
            "employee_deductions", "income_tax", "employee__id",
            "employee__first_name", "employee__last_name",
        )
    )
    if not slips:
        return {"error": "no_payslips"}

    # Détection statistique simple (sans LLM) : net hors écart-type 2σ.
    nets = [float(s.net_amount or 0) for s in slips]
    avg = sum(nets) / len(nets)
    var = sum((n - avg) ** 2 for n in nets) / len(nets)
    std = var ** 0.5

    anomalies = []
    for slip in slips:
        n = float(slip.net_amount or 0)
        if std > 0 and abs(n - avg) > 2 * std:
            anomalies.append({
                "payslip_id": str(slip.id),
                "employee": f"{slip.employee.first_name} {slip.employee.last_name}".strip(),
                "net_amount": n,
                "deviation": round((n - avg) / std, 2),
                "type": "outlier_net",
            })

    return {
        "period": period.label,
        "average_net": round(avg, 2),
        "std_dev": round(std, 2),
        "outliers": anomalies,
        "total_payslips": len(slips),
    }


@registry.tool(
    name="payroll.simulate_salary",
    description="Simule un salaire à partir d'un brut et d'un profil de paie.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "profile_id": {"type": "string"},
            "base_salary": {"type": "number"},
            "currency": {"type": "string", "default": "XOF"},
        },
        "required": ["profile_id", "base_salary"],
        "additionalProperties": False,
    },
    module="payroll",
)
def simulate_salary(
    *,
    tenant,
    user,
    profile_id: str,
    base_salary: float,
    currency: str = "XOF",
    **_,
) -> Dict[str, Any]:
    """
    Lance le moteur de calcul SANS persister : on prépare un Payslip "fantôme"
    en mémoire. Permet à un user de voir l'impact d'un salaire avant
    embauche.
    """
    from payroll.models import (
        EmployeePayrollProfile,
        PayrollPeriod,
        PayrollPeriodStatus,
        PayrollProfile,
        Payslip,
    )
    from payroll.services.engine import PayrollEngine, q2

    profile = PayrollProfile.objects.filter(tenant=tenant, id=profile_id).first()
    if profile is None:
        return {"error": "profile_not_found"}

    period = (
        PayrollPeriod.objects
        .filter(tenant=tenant, status=PayrollPeriodStatus.OPEN)
        .order_by("-year", "-month")
        .first()
    )
    if period is None:
        return {"error": "no_open_period"}

    # On simule sans toucher la base : objet en mémoire.
    fake_emp_profile = EmployeePayrollProfile(
        tenant=tenant,
        employee_id=None,
        profile=profile,
        base_salary=Decimal(str(base_salary)),
        currency=currency,
        valid_from=period.date_start,
    )
    fake_payslip = Payslip(
        tenant=tenant, period=period,
        employee_profile=fake_emp_profile,
    )
    engine = PayrollEngine(period)
    result = engine._calculate(fake_payslip)  # pylint: disable=protected-access
    return {
        "base_salary": float(result.base_salary),
        "gross": float(result.gross_amount),
        "deductions": float(result.employee_deductions),
        "employer_charges": float(result.employer_charges),
        "net": float(result.net_amount),
        "lines": [
            {
                "code": ln.item_code, "label": ln.label, "kind": ln.kind,
                "base": float(ln.base_amount), "rate": float(ln.rate),
                "amount": float(ln.amount),
            }
            for ln in result.lines
        ],
    }


# --------------------------------------------------------------------------- #
# Sérialisation interne
# --------------------------------------------------------------------------- #
def _serialize_payslip_for_ai(slip) -> Dict[str, Any]:
    return {
        "slip_number": slip.slip_number,
        "employee": str(slip.employee),
        "period": slip.period.label if slip.period else None,
        "gross_amount": float(slip.gross_amount or 0),
        "deductions": float(slip.employee_deductions or 0),
        "net_amount": float(slip.net_amount or 0),
        "currency": slip.currency,
        "lines": [
            {
                "label": ln.label,
                "kind": ln.kind,
                "base_amount": float(ln.base_amount or 0),
                "rate": float(ln.rate or 0),
                "amount": float(ln.amount or 0),
            }
            for ln in slip.lines.all()
        ],
    }
