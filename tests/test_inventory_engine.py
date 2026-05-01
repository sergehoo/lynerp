"""
Tests stock : un mouvement IN/OUT met bien à jour Inventory et déclenche
les alertes seuil.
"""
from __future__ import annotations

from datetime import datetime, timezone as dt_tz
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import (
    Article,
    Inventory,
    MovementType,
    StockAlert,
    StockAlertStatus,
    StockMovement,
    Warehouse,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def stock_setup(tenant_a):
    art = Article.objects.create(
        tenant=tenant_a, sku="ART-001", name="Article test",
        purchase_price=Decimal("100"), sale_price=Decimal("150"),
        min_stock=Decimal("10"), max_stock=Decimal("100"),
    )
    wh = Warehouse.objects.create(tenant=tenant_a, code="WH1", name="Entrepôt 1")
    return {"art": art, "wh": wh}


def test_movement_in_increases_stock(stock_setup, tenant_a):
    StockMovement.objects.create(
        tenant=tenant_a,
        article=stock_setup["art"],
        warehouse=stock_setup["wh"],
        movement_type=MovementType.IN,
        quantity=Decimal("50"),
        movement_date=timezone.now(),
    )
    inv = Inventory.objects.get(
        tenant=tenant_a,
        article=stock_setup["art"],
        warehouse=stock_setup["wh"],
    )
    assert inv.quantity == Decimal("50")


def test_low_stock_triggers_alert(stock_setup, tenant_a):
    # Entrée : 12, sortie : 7 → reste 5 (< min_stock=10) → alerte LOW_STOCK
    StockMovement.objects.create(
        tenant=tenant_a, article=stock_setup["art"], warehouse=stock_setup["wh"],
        movement_type=MovementType.IN, quantity=Decimal("12"),
        movement_date=timezone.now(),
    )
    StockMovement.objects.create(
        tenant=tenant_a, article=stock_setup["art"], warehouse=stock_setup["wh"],
        movement_type=MovementType.OUT, quantity=Decimal("7"),
        movement_date=timezone.now(),
    )
    alerts = StockAlert.objects.filter(
        tenant=tenant_a, article=stock_setup["art"], status=StockAlertStatus.OPEN,
    )
    assert alerts.count() >= 1
    assert any(a.alert_type == "LOW_STOCK" for a in alerts)


def test_out_of_stock_alert(stock_setup, tenant_a):
    StockMovement.objects.create(
        tenant=tenant_a, article=stock_setup["art"], warehouse=stock_setup["wh"],
        movement_type=MovementType.IN, quantity=Decimal("5"),
        movement_date=timezone.now(),
    )
    StockMovement.objects.create(
        tenant=tenant_a, article=stock_setup["art"], warehouse=stock_setup["wh"],
        movement_type=MovementType.OUT, quantity=Decimal("5"),
        movement_date=timezone.now(),
    )
    alerts = StockAlert.objects.filter(
        tenant=tenant_a, article=stock_setup["art"], status=StockAlertStatus.OPEN,
    )
    assert any(a.alert_type == "OUT_OF_STOCK" for a in alerts)
