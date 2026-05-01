"""
Moteur de stock : applique un mouvement, met à jour Inventory, déclenche
les alertes seuil.

Source de vérité : ``StockMovement``. ``Inventory`` est un cache calculé.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from inventory.models import (
    Article,
    Inventory,
    MovementType,
    StockAlert,
    StockAlertStatus,
    StockAlertType,
    StockMovement,
    Warehouse,
)

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


class StockError(Exception):
    """Erreur métier (rupture, transfert invalide, etc.)."""


@transaction.atomic
def apply_movement(movement: StockMovement) -> StockMovement:
    """
    Applique le mouvement déjà persisté : met à jour Inventory + alertes.
    À appeler APRÈS save() (ou en post_save signal).
    """
    if movement.movement_type == MovementType.TRANSFER:
        if not movement.target_warehouse_id:
            raise StockError("Transfert sans entrepôt de destination.")
        _adjust_inventory(movement, movement.warehouse, -movement.quantity)
        _adjust_inventory(movement, movement.target_warehouse, +movement.quantity)
    elif movement.movement_type == MovementType.IN:
        _adjust_inventory(movement, movement.warehouse, +movement.quantity)
    elif movement.movement_type == MovementType.OUT:
        _adjust_inventory(movement, movement.warehouse, -movement.quantity)
    elif movement.movement_type == MovementType.ADJUST:
        # On force la quantité à la valeur cible (signed via unit_cost ?
        # ici on traite ADJUST comme un delta).
        _adjust_inventory(movement, movement.warehouse, movement.quantity)
    return movement


def _adjust_inventory(
    movement: StockMovement, warehouse: Warehouse, delta: Decimal,
) -> Inventory:
    inv, _ = Inventory.objects.select_for_update().get_or_create(
        tenant=movement.tenant,
        article=movement.article,
        warehouse=warehouse,
        defaults={"quantity": ZERO},
    )
    inv.quantity = (inv.quantity or ZERO) + Decimal(delta)
    inv.last_movement_at = movement.movement_date or timezone.now()
    if inv.quantity < 0:
        # On accepte mais on déclenche une alerte de rupture (négatif possible
        # en cas de désynchro ; à corriger via un inventaire physique).
        logger.warning(
            "Stock négatif détecté article=%s warehouse=%s qty=%s",
            movement.article_id, warehouse.id, inv.quantity,
        )
    inv.save()
    _check_alerts(movement.article, warehouse, inv)
    return inv


def _check_alerts(article: Article, warehouse: Warehouse, inv: Inventory) -> None:
    """Crée/déclenche les alertes selon les seuils définis sur l'article."""
    if inv.quantity <= ZERO:
        _create_alert(article, warehouse, inv, StockAlertType.OUT_OF_STOCK)
    elif article.min_stock and inv.quantity <= article.min_stock:
        _create_alert(article, warehouse, inv, StockAlertType.LOW_STOCK)
    elif article.max_stock and inv.quantity >= article.max_stock:
        _create_alert(article, warehouse, inv, StockAlertType.OVERSTOCK)


def _create_alert(article, warehouse, inv, alert_type) -> None:
    # Évite les doublons : si une alerte ouverte existe déjà pour le même
    # article/entrepôt/type, on la garde.
    exists = StockAlert.objects.filter(
        tenant=article.tenant,
        article=article, warehouse=warehouse,
        alert_type=alert_type, status=StockAlertStatus.OPEN,
    ).exists()
    if exists:
        return
    StockAlert.objects.create(
        tenant=article.tenant,
        article=article, warehouse=warehouse,
        alert_type=alert_type,
        quantity_at_alert=inv.quantity,
    )


def reorder_quantity(article: Article, current_qty: Decimal) -> Decimal:
    """
    Calcule une quantité de réapprovisionnement suggérée :
    cible = max_stock (ou min*2 si max=0), commande = cible - current_qty.
    """
    target = article.max_stock or (article.min_stock * 2)
    qty = (target or Decimal("0")) - (current_qty or Decimal("0"))
    return max(qty, Decimal("0"))
