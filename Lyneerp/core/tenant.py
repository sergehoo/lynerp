"""
Résolveur de tenant unifié pour LYNEERP.

Un seul endroit décide d'où vient l'identifiant tenant pour une requête.
Toutes les apps doivent utiliser :

    from Lyneerp.core.tenant import resolve_tenant_from_request

au lieu de réimplémenter leur propre logique.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)

TENANT_HEADER = "HTTP_X_TENANT_ID"
DEFAULT_TENANT_SUBDOMAIN_REGEX = r"^(?P<tenant>[a-z0-9-]+)\."


def _is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _subdomain_regex() -> re.Pattern[str]:
    pattern = getattr(
        settings, "TENANT_SUBDOMAIN_REGEX", DEFAULT_TENANT_SUBDOMAIN_REGEX
    )
    return re.compile(pattern, re.IGNORECASE)


def infer_tenant_from_host(host: str) -> Optional[str]:
    """
    Extrait un identifiant tenant depuis un nom d'hôte.

    Renvoie None pour localhost / IP / nom d'hôte sans point.
    """
    if not host:
        return None

    host = host.split(":", 1)[0].lower().strip()
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return None
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return None

    match = _subdomain_regex().match(host)
    if match:
        return match.group("tenant")

    if "." not in host:
        return None
    return host.split(".", 1)[0]


def _safe_resolve(identifier: Optional[str]):
    """
    Importation locale pour éviter l'import circulaire au chargement Django.
    """
    if not identifier:
        return None
    try:
        from tenants.models import Tenant
    except Exception:  # noqa: BLE001
        logger.exception("tenants app not loaded yet")
        return None

    value = str(identifier).strip()
    if not value:
        return None

    if _is_uuid(value):
        tenant = Tenant.objects.filter(id=value).only("id", "slug", "name", "is_active").first()
        if tenant:
            return tenant

    tenant = (
        Tenant.objects
        .filter(slug=value)
        .only("id", "slug", "name", "is_active")
        .first()
    )
    if tenant:
        return tenant

    if hasattr(Tenant, "domain"):
        tenant = (
            Tenant.objects
            .filter(domain=value)
            .only("id", "slug", "name", "is_active")
            .first()
        )
        if tenant:
            return tenant

    return None


def resolve_tenant(identifier: Optional[str]):
    """
    Résout une instance Tenant à partir d'un identifiant souple :
    UUID, slug, ou domain. Renvoie None si introuvable.
    """
    return _safe_resolve(identifier)


def resolve_tenant_from_request(request: HttpRequest):
    """
    Ordre de résolution :

      1. ``request.tenant`` déjà posé par un middleware
      2. Header ``X-Tenant-Id`` (UUID ou slug)
      3. Session ``tenant_id`` (ou ``settings.TENANT_SESSION_KEY``)
      4. Sous-domaine selon ``TENANT_SUBDOMAIN_REGEX``
      5. Claims OIDC ``request.oidc.tenant`` / ``tenant_id``
      6. ``settings.DEFAULT_TENANT`` (slug ou UUID)
    """
    if request is None:
        return None

    cached = getattr(request, "tenant", None)
    if cached is not None:
        return cached

    # 2) Header HTTP
    ident = (
        request.META.get(TENANT_HEADER)
        or request.headers.get("X-Tenant-Id")
    )
    tenant = _safe_resolve(ident)
    if tenant:
        return tenant

    # 3) Session
    if hasattr(request, "session"):
        session_key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
        ident = request.session.get("tenant_id") or request.session.get(session_key)
        tenant = _safe_resolve(ident)
        if tenant:
            return tenant

    # 4) Host
    host = request.get_host() if hasattr(request, "get_host") else ""
    ident = infer_tenant_from_host(host)
    tenant = _safe_resolve(ident)
    if tenant:
        return tenant

    # 5) OIDC claims
    oidc = getattr(request, "oidc", None) or {}
    if isinstance(oidc, dict):
        ident = oidc.get("tenant") or oidc.get("tenant_id")
        tenant = _safe_resolve(ident)
        if tenant:
            return tenant

    # 6) Default
    ident = getattr(settings, "DEFAULT_TENANT", None)
    return _safe_resolve(ident)


def get_tenant_id(request: HttpRequest) -> Optional[str]:
    """Retourne l'UUID stringifié du tenant courant ou None."""
    tenant = getattr(request, "tenant", None) or resolve_tenant_from_request(request)
    return str(tenant.id) if tenant else None
