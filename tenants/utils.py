# tenants/utils.py
from __future__ import annotations
import re
from typing import Optional
from uuid import UUID

from django.conf import settings
from tenants.models import Tenant

_SUBDOMAIN_RE = re.compile(
    getattr(settings, "TENANT_SUBDOMAIN_REGEX", r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"),
    re.I,
)

def _is_uuid(val: str) -> bool:
    try:
        UUID(str(val))
        return True
    except Exception:
        return False

def infer_tenant_from_host(host: str) -> Optional[str]:
    host = (host or "").split(":")[0]
    m = _SUBDOMAIN_RE.match(host)
    if m:
        return m.group("tenant")
    # fallback plus permissif (ex: acme.example.com -> "acme")
    if host and "." in host:
        return host.split(".")[0]
    return None

def resolve_tenant(identifier: Optional[str]) -> Optional[Tenant]:
    """
    Résout une instance Tenant à partir d’un identifiant souple :
    - UUID (id)
    - slug (champ unique conseillé)
    - domain (si tu l’as dans ton modèle)
    """
    if not identifier:
        return None
    val = str(identifier).strip()

    # 1) par UUID
    if _is_uuid(val):
        t = Tenant.objects.filter(id=val).first()
        if t:
            return t

    # 2) par slug
    t = Tenant.objects.filter(slug=val).first()
    if t:
        return t

    # 3) par domain (facultatif si tu as ce champ)
    if hasattr(Tenant, "domain"):
        t = Tenant.objects.filter(domain=val).first()
        if t:
            return t

    return None

def get_tenant_from_request(request) -> Optional[Tenant]:
    """
    Ordre de résolution :
      1) X-Tenant-Id (id ou slug)
      2) session 'tenant_id' / TENANT_SESSION_KEY
      3) sous-domaine
      4) DEFAULT_TENANT (slug ou id)
    """
    # header
    ident = request.META.get("HTTP_X_TENANT_ID") or request.headers.get("X-Tenant-Id")
    if ident:
        t = resolve_tenant(ident)
        if t:
            return t

    # session
    ident = request.session.get("tenant_id") or request.session.get(getattr(settings, "TENANT_SESSION_KEY", "current_tenant"))
    if ident:
        t = resolve_tenant(ident)
        if t:
            return t

    # host
    ident = infer_tenant_from_host(request.get_host())
    if ident:
        t = resolve_tenant(ident)
        if t:
            return t

    # default
    ident = getattr(settings, "DEFAULT_TENANT", None)
    if ident:
        t = resolve_tenant(ident)
        if t:
            return t

    return None