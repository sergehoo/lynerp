"""Signal post_save sur StockMovement → met à jour Inventory + alertes."""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from inventory.models import StockMovement
from inventory.services.stock_engine import apply_movement


@receiver(post_save, sender=StockMovement)
def on_movement_saved(sender, instance: StockMovement, created, **kwargs):
    if not created:
        # On ne ré-applique pas un mouvement édité (immuable par convention).
        return
    apply_movement(instance)
