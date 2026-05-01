"""
Registre des calculs KPI.

Chaque KPI est une fonction qui prend un tenant et renvoie une valeur
(scalaire ou structurée). On les agrège dans un dict pour les vues web/API.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

_KPIS: Dict[str, Callable[..., Any]] = {}


def register_kpi(code: str):
    def _wrap(fn):
        _KPIS[code] = fn
        return fn
    return _wrap


def get_kpi(code: str) -> Callable[..., Any] | None:
    return _KPIS.get(code)


def list_kpis() -> Dict[str, str]:
    return {code: (fn.__doc__ or "").strip().split("\n")[0] for code, fn in _KPIS.items()}


def compute(code: str, *, tenant, **kwargs) -> Any:
    fn = _KPIS.get(code)
    if fn is None:
        return {"error": f"KPI '{code}' inconnu."}
    try:
        return fn(tenant=tenant, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("KPI %s failed", code)
        return {"error": str(exc)}


# --------------------------------------------------------------------------- #
# KPIs natifs
# --------------------------------------------------------------------------- #
@register_kpi("hr.headcount")
def hr_headcount(*, tenant, **_) -> Dict[str, Any]:
    """Effectif actif total."""
    try:
        from hr.models import Employee

        n = Employee.objects.filter(tenant=tenant, is_active=True).count()
        return {"value": n, "label": "Effectif actif"}
    except Exception:  # noqa: BLE001
        return {"value": 0, "label": "Effectif actif"}


@register_kpi("hr.new_hires_30d")
def hr_new_hires(*, tenant, **_) -> Dict[str, Any]:
    """Nouvelles embauches sur 30 jours."""
    try:
        from hr.models import Employee

        since = date.today() - timedelta(days=30)
        n = Employee.objects.filter(tenant=tenant, hire_date__gte=since).count()
        return {"value": n, "label": "Nouvelles embauches 30j"}
    except Exception:  # noqa: BLE001
        return {"value": 0}


@register_kpi("payroll.total_net_last_period")
def payroll_total_net(*, tenant, **_) -> Dict[str, Any]:
    """Net total versé sur la dernière période clôturée."""
    try:
        from django.db.models import Sum
        from payroll.models import PayrollPeriod, PayrollPeriodStatus, Payslip

        last = (
            PayrollPeriod.objects
            .filter(tenant=tenant, status=PayrollPeriodStatus.CLOSED)
            .order_by("-year", "-month").first()
        )
        if last is None:
            return {"value": 0, "label": "Aucune période clôturée"}
        total = Payslip.objects.filter(
            tenant=tenant, period=last,
        ).aggregate(s=Sum("net_amount"))["s"] or 0
        return {"value": float(total), "label": f"Net payé — {last.label}"}
    except Exception:  # noqa: BLE001
        return {"value": 0}


@register_kpi("crm.pipeline_open_amount")
def crm_pipeline_amount(*, tenant, **_) -> Dict[str, Any]:
    """Montant cumulé des opportunités ouvertes."""
    try:
        from django.db.models import Sum
        from crm.models import Opportunity, OpportunityStatus

        v = Opportunity.objects.filter(
            tenant=tenant, status=OpportunityStatus.OPEN,
        ).aggregate(s=Sum("amount"))["s"] or 0
        return {"value": float(v), "label": "Pipeline ouvert"}
    except Exception:  # noqa: BLE001
        return {"value": 0}


@register_kpi("inventory.open_alerts")
def inventory_alerts(*, tenant, **_) -> Dict[str, Any]:
    """Nombre d'alertes stock ouvertes."""
    try:
        from inventory.models import StockAlert, StockAlertStatus

        n = StockAlert.objects.filter(
            tenant=tenant, status=StockAlertStatus.OPEN,
        ).count()
        return {"value": n, "label": "Alertes stock ouvertes"}
    except Exception:  # noqa: BLE001
        return {"value": 0}


@register_kpi("projects.active_count")
def projects_active(*, tenant, **_) -> Dict[str, Any]:
    """Projets actifs."""
    try:
        from projects.models import Project, ProjectStatus

        n = Project.objects.filter(tenant=tenant, status=ProjectStatus.ACTIVE).count()
        return {"value": n, "label": "Projets actifs"}
    except Exception:  # noqa: BLE001
        return {"value": 0}


@register_kpi("ai.actions_pending")
def ai_actions_pending(*, tenant, **_) -> Dict[str, Any]:
    """Actions IA en attente de validation."""
    try:
        from ai_assistant.models import AIAction, AIActionStatus

        n = AIAction.objects.filter(
            tenant=tenant, status=AIActionStatus.PROPOSED,
        ).count()
        return {"value": n, "label": "Actions IA à valider"}
    except Exception:  # noqa: BLE001
        return {"value": 0}
