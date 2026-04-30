"""
Idempotence des paiements.

Garantit que la contrainte ``uniq_payment_idempotency_per_tenant`` empêche
deux paiements simultanés du même tenant de partager une clé d'idempotence.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import IntegrityError

from finance.models import Account, AccountType, FiscalYear, Invoice, Partner, Payment, PaymentMethod, PaymentStatus
from finance.models import CompanyFinanceProfile  # noqa: F401  (assure auto-load)

pytestmark = pytest.mark.django_db


def _make_partner(tenant):
    return Partner.objects.create(
        tenant=tenant, code="P1", name="Acme", type="CUSTOMER",
    )


def _make_invoice(tenant, partner):
    fy = FiscalYear.objects.create(
        tenant=tenant, name="FY2026",
        date_start=date(2026, 1, 1), date_end=date(2026, 12, 31),
    )
    # NB: Invoice a beaucoup de champs ; on s'appuie sur les valeurs par défaut.
    return Invoice.objects.create(
        tenant=tenant, partner=partner,
        invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
        total_amount=1000,
    )


def _make_payment(tenant, invoice, **kwargs):
    defaults = dict(
        tenant=tenant, invoice=invoice,
        method=PaymentMethod.BANK if hasattr(PaymentMethod, "BANK") else "BANK",
        status=PaymentStatus.PENDING,
        amount=500,
    )
    defaults.update(kwargs)
    return Payment.objects.create(**defaults)


def test_idempotency_blocks_duplicates(tenant_a):
    partner = _make_partner(tenant_a)
    invoice = _make_invoice(tenant_a, partner)

    _make_payment(tenant_a, invoice, idempotency_key="abc-123")

    with pytest.raises(IntegrityError):
        _make_payment(tenant_a, invoice, idempotency_key="abc-123")


def test_idempotency_scoped_per_tenant(tenant_a, tenant_b):
    pa = _make_partner(tenant_a)
    pb = _make_partner(tenant_b)
    ia = _make_invoice(tenant_a, pa)
    ib = _make_invoice(tenant_b, pb)

    _make_payment(tenant_a, ia, idempotency_key="abc-123")
    # Même clé sur un autre tenant : autorisé.
    _make_payment(tenant_b, ib, idempotency_key="abc-123")


def test_empty_key_allows_multiple_payments(tenant_a):
    partner = _make_partner(tenant_a)
    invoice = _make_invoice(tenant_a, partner)

    _make_payment(tenant_a, invoice, idempotency_key="")
    _make_payment(tenant_a, invoice, idempotency_key="")
    # Pas d'IntegrityError : la contrainte exclut idempotency_key="".
    assert Payment.objects.filter(invoice=invoice).count() == 2
