"""
Vérifie la robustesse de la hash chain ``AuditEvent``.

- Le hash est posé en une seule transaction (pas de double-write).
- Toute altération d'un champ doit invalider ``verify_chain()``.
- Le ``prev_hash`` chaîne bien le précédent événement du même tenant.
"""
from __future__ import annotations

import pytest

from finance.models import AuditAction, AuditEvent

pytestmark = pytest.mark.django_db


def _create_event(tenant, **overrides):
    payload = dict(
        tenant=tenant,
        action=AuditAction.CREATE,
        model_label="finance.Invoice",
        object_id="42",
        object_repr="INV-2026-0001",
        before={},
        after={"total": "1000.00"},
        meta={"source": "API", "ip": "127.0.0.1"},
    )
    payload.update(overrides)
    return AuditEvent.objects.create(**payload)


def test_event_hash_is_set_on_create(tenant_a):
    evt = _create_event(tenant_a)
    assert evt.event_hash, "event_hash doit être posé au create."
    assert len(evt.event_hash) == 64, "SHA-256 hex = 64 chars."


def test_chain_links_to_previous_event(tenant_a):
    first = _create_event(tenant_a)
    second = _create_event(tenant_a, object_id="43")
    assert second.prev_hash == first.event_hash, (
        "Le 2e événement doit pointer sur le hash du 1er pour le même tenant."
    )


def test_chain_isolation_per_tenant(tenant_a, tenant_b):
    a1 = _create_event(tenant_a, object_id="1")
    b1 = _create_event(tenant_b, object_id="1")
    # Pas de "fuite" de chaîne d'un tenant à l'autre.
    assert a1.prev_hash == ""
    assert b1.prev_hash == ""


def test_verify_chain_detects_tampering(tenant_a):
    evt = _create_event(tenant_a)
    assert evt.verify_chain() is True

    # Altération directe en DB : on contourne save() pour ne PAS recalculer le hash.
    AuditEvent.objects.filter(pk=evt.pk).update(after={"total": "9999.99"})
    evt.refresh_from_db()
    assert evt.verify_chain() is False, (
        "Toute modification doit invalider verify_chain()."
    )


def test_update_does_not_change_hash(tenant_a):
    evt = _create_event(tenant_a)
    original = evt.event_hash
    # Modification "légitime" via save : on ne recalcule PAS le hash en update.
    evt.object_repr = "INV-2026-0001-modified"
    evt.save()
    evt.refresh_from_db()
    assert evt.event_hash == original
