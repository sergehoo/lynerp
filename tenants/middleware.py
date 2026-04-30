"""
Middleware multi-tenant unifié pour LYNEERP.

Un SEUL middleware (``TenantMiddleware``) résout le tenant courant pour chaque
requête. La résolution est déléguée à ``Lyneerp.core.tenant.resolve_tenant_from_request``
afin de garder la logique factorisée.

Comportements clés :

- Si on trouve un tenant : on attache ``request.tenant`` (instance) et
  ``request.tenant_id`` (UUID stringifié), on synchronise la session, et on
  pose ``HTTP_X_TENANT_ID`` pour les viewsets DRF.
- Si on n'en trouve pas et que la requête vise ``/api/``, on retourne 403 JSON
  avec un code d'erreur stable. Pour les autres requêtes, on laisse passer
  (``request.tenant = None``) afin que les vues de login / OIDC / static
  restent accessibles sans tenant.
- Les chemins exemptés (``settings.TENANT_EXEMPT_PATHS``) ne déclenchent jamais
  de blocage. Par défaut : admin, healthz, login, OIDC, static, schema, docs.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import JsonResponse

from Lyneerp.core.tenant import resolve_tenant_from_request

logger = logging.getLogger(__name__)


DEFAULT_EXEMPT_PREFIXES = (
    "/admin/",
    "/healthz",
    "/static/",
    "/media/",
    "/login/",
    "/logout/",
    "/oidc/",
    "/api/schema",
    "/api/docs",
    "/api/redoc",
    "/api/auth/whoami",
    "/api/auth/exchange",
    "/api/auth/keycloak",
)


def _path_is_exempt(path: str) -> bool:
    exempt = tuple(getattr(settings, "TENANT_EXEMPT_PATHS", DEFAULT_EXEMPT_PREFIXES))
    return any(path.startswith(prefix) for prefix in exempt)


class TenantMiddleware:
    """
    Middleware Django (style fonction-callable) pour LYNEERP.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.session_key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")

    def __call__(self, request):
        tenant = resolve_tenant_from_request(request)
        request.tenant = tenant
        request.tenant_id = str(tenant.id) if tenant else None

        if tenant is not None:
            # Synchronise la session pour les requêtes suivantes.
            if hasattr(request, "session"):
                request.session[self.session_key] = request.tenant_id

            # Permet à DRF & permissions de s'appuyer sur le header.
            if "HTTP_X_TENANT_ID" not in request.META:
                request.META["HTTP_X_TENANT_ID"] = request.tenant_id
        else:
            # Bloque les requêtes API sans tenant — on évite tout fall-through silencieux.
            path = getattr(request, "path", "") or ""
            if path.startswith("/api/") and not _path_is_exempt(path):
                logger.info(
                    "[TenantMiddleware] Tenant introuvable pour API path=%s host=%s",
                    path,
                    request.get_host() if hasattr(request, "get_host") else "?",
                )
                return JsonResponse(
                    {
                        "detail": "Organisation introuvable pour cette requête.",
                        "code": "tenant_not_found",
                    },
                    status=403,
                )

        return self.get_response(request)
