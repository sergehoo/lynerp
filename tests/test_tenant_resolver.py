"""
Tests unitaires du résolveur de tenant.
"""
from __future__ import annotations

import pytest
from django.test import RequestFactory

from Lyneerp.core.tenant import (
    infer_tenant_from_host,
    resolve_tenant,
    resolve_tenant_from_request,
)

pytestmark = pytest.mark.django_db


def test_infer_tenant_from_subdomain(settings):
    settings.TENANT_SUBDOMAIN_REGEX = r"^(?P<tenant>[a-z0-9-]+)\.lyneerp\.test$"
    assert infer_tenant_from_host("acme.lyneerp.test") == "acme"


def test_infer_tenant_skips_localhost():
    assert infer_tenant_from_host("localhost") is None
    assert infer_tenant_from_host("127.0.0.1") is None


def test_resolve_tenant_by_slug(tenant_a):
    obj = resolve_tenant(tenant_a.slug)
    assert obj is not None
    assert obj.id == tenant_a.id


def test_resolve_tenant_by_uuid(tenant_a):
    obj = resolve_tenant(str(tenant_a.id))
    assert obj is not None
    assert obj.id == tenant_a.id


def test_resolve_tenant_unknown():
    assert resolve_tenant("nope-i-do-not-exist") is None


def test_request_resolution_uses_header(tenant_a):
    rf = RequestFactory()
    req = rf.get("/api/rh/employees/", HTTP_X_TENANT_ID=tenant_a.slug)
    obj = resolve_tenant_from_request(req)
    assert obj is not None
    assert obj.id == tenant_a.id
