# tenants/utils.py
from typing import Optional
from django.db.models import Q
from tenants.models import Tenant


def resolve_tenant(tenant_hint: Optional[str]) -> Optional[Tenant]:
    """
    Accepte: UUID (id), slug, domaine (ex: acme.lyneerp.com).
    Retourne l'objet Tenant ou None.
    """
    if not tenant_hint:
        return None

    # Essaye par id (UUID)
    try:
        return Tenant.objects.get(id=tenant_hint)
    except Exception:
        pass

    # Essaye par slug
    try:
        return Tenant.objects.get(slug=tenant_hint)
    except Tenant.DoesNotExist:
        pass

    # Essaye par domain exact ou domain sans port
    try:
        clean = str(tenant_hint).split(":")[0]
        return Tenant.objects.get(Q(domain=tenant_hint) | Q(domain=clean))
    except Tenant.DoesNotExist:
        return None
