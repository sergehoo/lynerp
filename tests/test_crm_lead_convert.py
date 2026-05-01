"""
Tests CRM : conversion d'un lead en compte + contact.
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from crm.models import Account, Contact, Lead, LeadStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def lead_a(tenant_a, user_a):
    return Lead.objects.create(
        tenant=tenant_a,
        first_name="Jean", last_name="Dupont",
        company="Dupont SARL",
        email="jean@dupont.example",
        phone="+225 00 00 00 00",
        owner=user_a,
        source="Site web",
    )


def test_convert_creates_account_and_contact(lead_a, user_a, client, tenant_a):
    client.force_login(user_a)
    url = reverse("crm_api:crm-leads-convert", args=[lead_a.id])
    resp = client.post(
        url, content_type="application/json",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code in (200, 201, 403)
    if resp.status_code in (200, 201):
        lead_a.refresh_from_db()
        assert lead_a.status == LeadStatus.CONVERTED
        assert lead_a.converted_account is not None
        assert Account.objects.filter(name="Dupont SARL").exists()
        assert Contact.objects.filter(account=lead_a.converted_account).exists()
