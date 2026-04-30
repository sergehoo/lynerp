"""
Vérifie que l'API ``/api/license/status/`` répond correctement et qu'elle
filtre bien par tenant (corrige le bug `tenant=slug` sur FK UUID).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_license_status_returns_active(client, license_a_active):
    """
    Avec une licence active, l'endpoint renvoie ``active=True``.
    """
    url = reverse("license:status")
    resp = client.get(f"{url}?tenant={license_a_active.tenant.slug}&module=rh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["plan"] == "Starter"
    assert data["seats_total"] == 5


def test_license_status_unknown_tenant(client):
    url = reverse("license:status")
    resp = client.get(f"{url}?tenant=does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "tenant_not_found"


def test_license_status_expired(client, license_a_expired):
    url = reverse("license:status")
    resp = client.get(f"{url}?tenant={license_a_expired.tenant.slug}&module=rh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is False
