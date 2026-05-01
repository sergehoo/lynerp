"""
Outils IA pour le module Stock / Achats.

- ``inventory.forecast_stockouts`` : prévision de rupture par article
  basée sur la consommation historique (déterministe, pas de LLM).
- ``inventory.recommend_reorder`` : suggestion de quantités à commander
  + brouillon de PO via AIAction (validation humaine).
- ``inventory.analyze_suppliers`` : analyse comparative des fournisseurs
  (LLM Ollama).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from django.db.models import Sum
from django.utils import timezone

from ai_assistant.models import AIAction
from ai_assistant.services.ollama import get_ollama
from ai_assistant.services.tool_registry import (
    RISK_READ,
    RISK_WRITE,
    get_tool_registry,
)

logger = logging.getLogger(__name__)
registry = get_tool_registry()


@registry.tool(
    name="inventory.forecast_stockouts",
    description="Prédit les ruptures de stock à venir selon la consommation historique.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {
            "horizon_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14},
            "history_days": {"type": "integer", "minimum": 7, "maximum": 365, "default": 30},
        },
        "additionalProperties": False,
    },
    module="inventory",
)
def forecast_stockouts(
    *,
    tenant,
    user,
    horizon_days: int = 14,
    history_days: int = 30,
    **_,
) -> Dict[str, Any]:
    from inventory.models import Article, Inventory, MovementType, StockMovement

    since = timezone.now() - timedelta(days=history_days)
    articles = Article.objects.filter(tenant=tenant, is_active=True)
    forecasts = []

    for art in articles:
        consumed = (
            StockMovement.objects
            .filter(
                tenant=tenant, article=art,
                movement_type=MovementType.OUT,
                movement_date__gte=since,
            )
            .aggregate(s=Sum("quantity"))["s"] or Decimal("0")
        )
        if not consumed:
            continue
        daily_consumption = Decimal(consumed) / Decimal(history_days)
        current_stock = (
            Inventory.objects
            .filter(tenant=tenant, article=art)
            .aggregate(s=Sum("quantity"))["s"] or Decimal("0")
        )
        if daily_consumption <= 0:
            continue
        days_until_stockout = float(current_stock / daily_consumption)
        if days_until_stockout > horizon_days:
            continue
        forecasts.append({
            "article_id": str(art.id),
            "sku": art.sku,
            "name": art.name,
            "current_stock": float(current_stock),
            "daily_consumption": float(daily_consumption),
            "days_until_stockout": round(days_until_stockout, 1),
            "lead_time_days": art.lead_time_days,
            "needs_immediate_action": days_until_stockout <= art.lead_time_days,
        })

    forecasts.sort(key=lambda r: r["days_until_stockout"])
    return {
        "horizon_days": horizon_days,
        "history_days": history_days,
        "predictions": forecasts,
        "count": len(forecasts),
    }


@registry.tool(
    name="inventory.recommend_reorder",
    description=(
        "Recommande des quantités de réapprovisionnement et propose une "
        "AIAction pour créer un brouillon de bon de commande."
    ),
    risk=RISK_WRITE,
    schema={
        "type": "object",
        "properties": {
            "supplier_id": {"type": "string"},
            "warehouse_id": {"type": "string"},
        },
        "required": ["warehouse_id"],
        "additionalProperties": False,
    },
    module="inventory",
)
def recommend_reorder(
    *,
    tenant,
    user,
    conversation,
    supplier_id: str | None = None,
    warehouse_id: str,
    **_,
) -> Dict[str, Any]:
    from inventory.models import Article, Inventory, Supplier, Warehouse
    from inventory.services.stock_engine import reorder_quantity

    warehouse = Warehouse.objects.filter(tenant=tenant, id=warehouse_id).first()
    if warehouse is None:
        return {"error": "warehouse_not_found"}

    supplier = None
    if supplier_id:
        supplier = Supplier.objects.filter(tenant=tenant, id=supplier_id).first()

    items_to_order = []
    for art in Article.objects.filter(tenant=tenant, is_active=True):
        inv = (
            Inventory.objects
            .filter(tenant=tenant, article=art, warehouse=warehouse)
            .first()
        )
        current = inv.quantity if inv else Decimal("0")
        if not art.min_stock or current > art.min_stock:
            continue
        qty = reorder_quantity(art, current)
        if qty <= 0:
            continue
        items_to_order.append({
            "article_id": str(art.id),
            "sku": art.sku,
            "name": art.name,
            "current_stock": float(current),
            "recommended_qty": float(qty),
            "estimated_unit_cost": float(art.purchase_price),
            "estimated_total": float(qty * (art.purchase_price or Decimal("0"))),
        })

    if not items_to_order:
        return {"items": [], "message": "Aucun réapprovisionnement nécessaire."}

    # Crée une AIAction pour générer un brouillon de PO.
    total_estimate = sum(i["estimated_total"] for i in items_to_order)
    action = AIAction.objects.create(
        tenant=tenant,
        conversation=conversation,
        proposed_by=user if (user and user.is_authenticated) else None,
        action_type="inventory.create_purchase_order",
        title=f"Bon de commande de réapprovisionnement ({len(items_to_order)} articles)",
        summary=(
            f"Création suggérée d'un bon de commande pour réapprovisionner "
            f"l'entrepôt {warehouse.code}. Total estimé : "
            f"**{total_estimate:,.2f}**."
        ),
        payload={
            "warehouse_id": str(warehouse.id),
            "supplier_id": str(supplier.id) if supplier else None,
            "items": items_to_order,
        },
        risk_level="MEDIUM",
        requires_double_approval=False,
    )

    return {
        "action_id": str(action.id),
        "items": items_to_order,
        "estimated_total": total_estimate,
        "_message": (
            f"Suggestion de réapprovisionnement créée — validation humaine "
            f"requise. Voir AIAction {action.id}."
        ),
    }


@registry.tool(
    name="inventory.analyze_suppliers",
    description="Analyse comparative des fournisseurs (volume, délais, notes).",
    risk=RISK_READ,
    schema={"type": "object", "properties": {}, "additionalProperties": False},
    module="inventory",
)
def analyze_suppliers(*, tenant, user, **_) -> Dict[str, Any]:
    from inventory.models import PurchaseOrder, Supplier

    payload = []
    for s in Supplier.objects.filter(tenant=tenant, is_active=True):
        po_count = PurchaseOrder.objects.filter(tenant=tenant, supplier=s).count()
        recent = PurchaseOrder.objects.filter(
            tenant=tenant, supplier=s,
        ).order_by("-order_date").values_list("status", flat=True)[:10]
        payload.append({
            "supplier": s.name,
            "rating": float(s.rating or 0),
            "po_count": po_count,
            "payment_terms_days": s.payment_terms_days,
            "recent_status": list(recent),
        })

    if not payload:
        return {"summary": "Aucun fournisseur actif.", "data": []}

    user_msg = (
        "Voici la liste des fournisseurs avec leurs statistiques. "
        "Produis une synthèse Markdown : forces, faiblesses, recommandations.\n\n"
        f"{payload}"
    )
    result = get_ollama().chat([
        {"role": "system", "content": "Tu es un acheteur senior."},
        {"role": "user", "content": user_msg},
    ])
    return {
        "summary_markdown": result.get("content", ""),
        "data": payload,
        "model": result.get("model"),
        "duration_ms": result.get("duration_ms"),
    }
