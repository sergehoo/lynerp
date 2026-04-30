"""
Tests de l'endpoint ``/api/auth/keycloak/login/``.

On mocke entièrement Keycloak avec ``responses`` ou ``unittest.mock`` pour
ne pas dépendre d'un serveur externe.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def patch_kc_settings(settings):
    settings.KEYCLOAK_BASE_URL = "https://sso.example.com"
    settings.KEYCLOAK_REALM = "lyneerp"
    settings.KEYCLOAK_CLIENT_ID = "rh-core"
    settings.KEYCLOAK_CLIENT_SECRET = None
    settings.KEYCLOAK_USE_REALM_PER_TENANT = False
    settings.OIDC_SESSION_KEY = "oidc_user"


def test_login_requires_credentials(client, patch_kc_settings):
    url = reverse("auth:keycloak-direct-login")
    resp = client.post(url, content_type="application/json", data="{}")
    assert resp.status_code == 400
    assert resp.json()["code"] == "missing_credentials"


def test_login_unknown_tenant(client, patch_kc_settings):
    url = reverse("auth:keycloak-direct-login")
    resp = client.post(
        url,
        content_type="application/json",
        data='{"username": "x", "password": "y", "tenant_id": "ghost"}',
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "tenant_not_found"


def test_login_refused_when_user_not_member(client, patch_kc_settings, tenant_b):
    url = reverse("auth:keycloak-direct-login")

    fake_resp_ok = type(
        "R", (), {
            "status_code": 200,
            "json": lambda self: {
                "access_token": "abc",
                "id_token": "def",
                "refresh_token": "ghi",
            },
        },
    )()

    with patch("tenants.auth_views.requests.post", return_value=fake_resp_ok), \
         patch(
             "tenants.auth_views.jose_jwt.get_unverified_claims",
             return_value={"sub": "kc-1", "email": "intruder@nope.example",
                           "preferred_username": "intruder"},
         ):
        resp = client.post(
            url,
            content_type="application/json",
            data=f'{{"username": "intruder", "password": "x", "tenant_id": "{tenant_b.slug}"}}',
        )

    assert resp.status_code == 403
    assert resp.json()["code"] == "tenant_access_denied"
