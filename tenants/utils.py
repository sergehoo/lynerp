"""
Helpers tenant — façade pour les apps qui veulent rester découplées de
``Lyneerp.core``.

Cette couche conserve l'API historique du projet (``resolve_tenant``,
``get_tenant_from_request``, ``infer_tenant_from_host``) mais déléguée à
l'unique implémentation dans ``Lyneerp.core.tenant``.
"""
from __future__ import annotations

from typing import Optional

from Lyneerp.core.tenant import (
    infer_tenant_from_host as _infer_tenant_from_host,
    resolve_tenant as _resolve_tenant,
    resolve_tenant_from_request as _resolve_from_request,
)
from tenants.models import Tenant


def infer_tenant_from_host(host: str) -> Optional[str]:
    return _infer_tenant_from_host(host)


def resolve_tenant(identifier: Optional[str]) -> Optional[Tenant]:
    return _resolve_tenant(identifier)


def get_tenant_from_request(request) -> Optional[Tenant]:
    return _resolve_from_request(request)


def get_user_membership(user, tenant: Tenant):
    """
    Renvoie ``TenantUser`` actif si l'utilisateur appartient au tenant.
    """
    if not user or not user.is_authenticated or tenant is None:
        return None
    from tenants.models import TenantUser

    return (
        TenantUser.objects
        .filter(user=user, tenant=tenant, is_active=True)
        .select_related("user", "tenant")
        .first()
    )


def user_can_access_tenant(user, tenant: Tenant) -> bool:
    """
    Booleen pratique : True si superuser ou membre actif.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return get_user_membership(user, tenant) is not None
