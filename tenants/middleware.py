# tenants/middleware.py
from __future__ import annotations

import re

import jwt
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from tenants.models import Tenant
from urllib.parse import urlparse


class CurrentTenant:
    slug: str | None = None
    obj: Tenant | None = None


class TenantSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")

    def __call__(self, request):
        request.tenant_id = request.session.get(self.key)
        return self.get_response(request)


TENANT_HEADER = "HTTP_X_TENANT_ID"
TENANT_SESSION_KEY = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
TENANT_REGEX = getattr(settings, "TENANT_SUBDOMAIN_REGEX", r"^(?P<tenant>[a-z0-9-]+)\.")


def _tenant_from_host(host: str) -> str | None:
    # ex: acme.rh.lyneerp.com -> "acme"
    m = re.match(TENANT_REGEX, host, re.IGNORECASE)
    if m:
        return m.group("tenant")
    return None


def _tenant_from_bearer(request) -> str | None:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        # On ne valide pas la signature ici (déjà fait par la vue/API si nécessaire),
        # on lit juste le claim pour orienter le tenant.
        payload = jwt.decode(token, options={"verify_signature": False})
        # 1) claim direct
        if "tenant" in payload:
            return payload["tenant"]
        # 2) groupe/role style "tenant:acme"
        roles = (payload.get("realm_access", {}) or {}).get("roles", [])
        for r in roles:
            if r.startswith("tenant:"):
                return r.split(":", 1)[1]
    except Exception:
        return None
    return None


class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 1) Host
        host = request.get_host().split(":")[0]
        tenant = _tenant_from_host(host)

        # 2) Header (si proxy/traefik/kong ajoute X-Tenant-Id)
        if not tenant:
            tenant = request.META.get(TENANT_HEADER)

        # 3) Token Bearer
        if not tenant:
            tenant = _tenant_from_bearer(request)

        # 4) Fallback : éventuellement une valeur par défaut (ex: "default")
        if not tenant:
            tenant = getattr(settings, "DEFAULT_TENANT", None)

        request.tenant_id = tenant
        # Si tu veux encore garder une session, ok, mais pas obligatoire :
        if hasattr(request, "session"):
            request.session[TENANT_SESSION_KEY] = tenant
