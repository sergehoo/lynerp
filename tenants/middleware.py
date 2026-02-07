
# tenants/middleware.py
from __future__ import annotations

import re
from typing import Callable

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from tenants.models import Tenant
from tenants.utils import resolve_tenant, get_tenant_from_request

SUBDOMAIN_RE = re.compile(getattr(
    settings,
    "TENANT_SUBDOMAIN_REGEX",
    r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"
), re.I)


class RequestTenantMiddleware:
    """
    Middleware corrigé pour résoudre correctement le tenant
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _from_host(self, host):
        m = SUBDOMAIN_RE.match((host or "").split(":")[0])
        if m:
            return m.group("tenant")
        return None

    def __call__(self, request):
        tenant_id = None

        # 1) Header X-Tenant-Id (priorité haute)
        tenant_id = request.META.get("HTTP_X_TENANT_ID")

        # 2) Session
        if not tenant_id:
            tenant_id = request.session.get("tenant_id") or request.session.get(
                getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
            )

        # 3) Host/sous-domaine
        if not tenant_id:
            tenant_id = self._from_host(request.get_host())

        # 4) Token JWT (si présent)
        if not tenant_id:
            tenant_id = self._tenant_from_bearer(request)

        # 5) Fallback
        if not tenant_id:
            tenant_id = getattr(settings, "DEFAULT_TENANT", None)

        # Résolution du tenant
        tenant_obj = resolve_tenant(tenant_id)
        request.tenant = tenant_obj
        request.tenant_id = tenant_id

        # Injection du header pour les vues API
        if tenant_id and "HTTP_X_TENANT_ID" not in request.META:
            request.META["HTTP_X_TENANT_ID"] = str(tenant_id)

        return self.get_response(request)

    def _tenant_from_bearer(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            # 1) claim direct
            if "tenant" in payload:
                return payload["tenant"]
            # 2) claim tenant_id
            if "tenant_id" in payload:
                return payload["tenant_id"]
            # 3) groupe/role style "tenant : acme"
            roles = (payload.get("realm_access", {}) or {}).get("roles", [])
            for r in roles:
                if r.startswith("tenant:"):
                    return r.split(":", 1)[1]
        except Exception:
            return None
        return None


class TenantResolutionMiddleware:
    """
    - Résout request.tenant (Tenant) et request.tenant_id (UUID str)
    - Stocke le tenant dans la session via TENANT_SESSION_KEY
    - Injecte HTTP_X_TENANT_ID pour DRF/permissions
    - Bloque /api/* et les requêtes JSON si tenant manquant
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.session_key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")

    def __call__(self, request):
        tenant = get_tenant_from_request(request)

        if tenant:
            request.tenant = tenant
            request.tenant_id = str(tenant.id)

            if hasattr(request, "session"):
                request.session[self.session_key] = request.tenant_id

            if "HTTP_X_TENANT_ID" not in request.META:
                request.META["HTTP_X_TENANT_ID"] = request.tenant_id
        else:
            request.tenant = None
            request.tenant_id = None

            accepts = (request.headers.get("Accept") or "")
            if request.path.startswith("/api/") or "application/json" in accepts:
                return JsonResponse(
                    {"detail": "Tenant introuvable", "code": "tenant_not_found"},
                    status=403
                )

        return self.get_response(request)
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
        # 2) groupe/role style "tenant : acme"
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

        # 4) Fallback : éventuellement une valeur par défaut (ex : "default")
        if not tenant:
            tenant = getattr(settings, "DEFAULT_TENANT", None)

        request.tenant_id = tenant
        # Si tu veux encore garder une session, ok, mais pas obligatoire :
        if hasattr(request, "session"):
            request.session[TENANT_SESSION_KEY] = tenant

