"""
Fixtures partagées par toute la suite pytest LYNEERP.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from tenants.models import License, Tenant, TenantUser

User = get_user_model()


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        slug="tenant-a",
        name="Tenant A",
        domain="a.lyneerp.local",
        is_active=True,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        slug="tenant-b",
        name="Tenant B",
        domain="b.lyneerp.local",
        is_active=True,
    )


@pytest.fixture
def user_a(db, tenant_a):
    user = User.objects.create_user(
        username="alice", email="alice@a.example", password="passw0rd!Secure"
    )
    TenantUser.objects.create(tenant=tenant_a, user=user, role="ADMIN", is_active=True)
    return user


@pytest.fixture
def user_b(db, tenant_b):
    user = User.objects.create_user(
        username="bob", email="bob@b.example", password="passw0rd!Secure"
    )
    TenantUser.objects.create(tenant=tenant_b, user=user, role="MEMBER", is_active=True)
    return user


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="root", email="root@example.com", password="root!Secure123"
    )


@pytest.fixture
def license_a_active(db, tenant_a):
    return License.objects.create(
        tenant=tenant_a,
        module="rh",
        plan="Starter",
        seats=5,
        valid_until=date.today() + timedelta(days=30),
        active=True,
    )


@pytest.fixture
def license_a_expired(db, tenant_a):
    return License.objects.create(
        tenant=tenant_a,
        module="rh",
        plan="Starter",
        seats=5,
        valid_until=date.today() - timedelta(days=1),
        active=True,
    )
