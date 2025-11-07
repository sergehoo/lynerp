# tenants/utils.py
from __future__ import annotations
import re
from typing import Optional
from django.conf import settings
from tenants.models import Tenant

SUBDOMAIN_RE = re.compile(
    getattr(settings, "TENANT_SUBDOMAIN_REGEX", r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"),
    re.I,
)

def _by_id_or_slug(value: str) -> Optional[Tenant]:
    if not value:
        return None
    # tente par ID UUID
    try:
        return Tenant.objects.filter(id=value).first()  # si value est uuid
    except Exception:
        pass
    # sinon par slug
    t = Tenant.objects.filter(slug=value).first()
    if t:
        return t
    # éventuel fallback par domaine si tu as un champ 'domain'
    try:
        return Tenant.objects.filter(domain=value).first()
    except Exception:
        return None

def infer_tenant_from_host(host: str) -> Optional[str]:
    host = (host or "").split(":")[0]
    m = SUBDOMAIN_RE.match(host)
    if m:
        return m.group("tenant")
    return None

def resolve_tenant_identifier(request) -> Optional[str]:
    # Ordre: champ fourni (header/corps) -> session -> host -> default
    h = (
        request.headers.get("X-Tenant-Id")
        or request.headers.get("X-Tenant-Slug")
        or request.session.get("tenant_id")
        or request.session.get(getattr(settings, "TENANT_SESSION_KEY", "current_tenant"))
    )
    if h:
        return str(h).strip()
    sub = infer_tenant_from_host(request.get_host())
    if sub:
        return sub
    return getattr(settings, "DEFAULT_TENANT", None)

def get_tenant_from_request(request) -> Optional[Tenant]:
    ident = resolve_tenant_identifier(request)
    if not ident:
        return None
    return _by_id_or_slug(ident)