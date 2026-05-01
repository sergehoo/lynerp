"""Outils transversaux (info tenant, recherche d'utilisateurs, etc.)."""
from __future__ import annotations

from typing import Any, Dict

from ai_assistant.services.tool_registry import (
    RISK_READ,
    get_tool_registry,
)

registry = get_tool_registry()


@registry.tool(
    name="general.tenant_info",
    description="Retourne les informations publiques de l'organisation courante.",
    risk=RISK_READ,
    schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    module="general",
)
def tenant_info(*, tenant, user, **_) -> Dict[str, Any]:
    if tenant is None:
        return {"error": "no_tenant"}
    return {
        "id": str(tenant.id),
        "slug": tenant.slug,
        "name": tenant.name,
        "currency": getattr(tenant, "currency", ""),
        "country": getattr(tenant, "billing_country", ""),
        "active_users": getattr(tenant, "active_users_count", 0),
    }


@registry.tool(
    name="general.who_am_i",
    description="Retourne les infos de l'utilisateur courant et ses permissions clés.",
    risk=RISK_READ,
    schema={"type": "object", "properties": {}, "additionalProperties": False},
    module="general",
)
def who_am_i(*, tenant, user, **_) -> Dict[str, Any]:
    from tenants.models import TenantUser

    membership = (
        TenantUser.objects
        .filter(user=user, tenant=tenant, is_active=True)
        .first()
        if user and user.is_authenticated and tenant
        else None
    )
    return {
        "username": getattr(user, "username", ""),
        "email": getattr(user, "email", ""),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "tenant_role": membership.role if membership else None,
    }
