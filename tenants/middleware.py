# tenants/middleware.py
from __future__ import annotations
import re, jwt
from typing import Callable, Optional
from django.conf import settings
from tenants.utils import resolve_tenant  # doit accepter slug/id et renvoyer None si non trouvé

TENANT_HEADER = "HTTP_X_TENANT_ID"
TENANT_SESSION_KEY = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
SUBDOMAIN_RE = re.compile(getattr(settings, "TENANT_SUBDOMAIN_REGEX",
                                  r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"), re.I)

def _from_host(host: str) -> Optional[str]:
    host = (host or "").split(":")[0]
    m = SUBDOMAIN_RE.match(host)
    return m.group("tenant") if m else None

def _from_bearer(request) -> Optional[str]:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        if "tenant" in payload: return payload["tenant"]
        if "tenant_id" in payload: return payload["tenant_id"]
        for r in (payload.get("realm_access", {}) or {}).get("roles", []):
            if r.startswith("tenant:"): return r.split(":", 1)[1]
    except Exception:
        pass
    return None

class TenantResolverMiddleware:
    """
    Résout request.tenant / request.tenant_id dans cet ordre:
    1) query param ?tenant=...
    2) header X-Tenant-Id
    3) session
    4) sous-domaine
    5) Bearer token (claims)
    6) DEFAULT_TENANT
    N'ENVOIE PAS de 403 ici — laisse les vues décider (whoami doit pouvoir répondre sans tenant).
    Injecte le header HTTP_X_TENANT_ID si trouvé.
    """
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        tenant_hint = (
            request.GET.get("tenant")
            or request.META.get(TENANT_HEADER)
            or request.session.get(TENANT_SESSION_KEY)
            or _from_host(request.get_host())
            or _from_bearer(request)
            or getattr(settings, "DEFAULT_TENANT", None)
        )

        tenant_obj = resolve_tenant(tenant_hint) if tenant_hint else None

        request.tenant = tenant_obj
        request.tenant_id = str(tenant_obj.id) if tenant_obj else None

        # Persiste en session (utile pour front en mode Session)
        if tenant_obj and hasattr(request, "session"):
            request.session[TENANT_SESSION_KEY] = request.tenant_id

        # Injecte le header pour DRF / permissions
        if request.tenant_id and TENANT_HEADER not in request.META:
            request.META[TENANT_HEADER] = request.tenant_id

        return self.get_response(request)
# # tenants/middleware.py
# from __future__ import annotations
#
# import re
# from typing import Callable
#
# import jwt
# from django.conf import settings
# from django.http import JsonResponse
# from django.utils.deprecation import MiddlewareMixin
# from tenants.models import Tenant
# from tenants.utils import resolve_tenant, get_tenant_from_request
#
# SUBDOMAIN_RE = re.compile(getattr(
#     settings,
#     "TENANT_SUBDOMAIN_REGEX",
#     r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"
# ), re.I)
#
#
# class RequestTenantMiddleware:
#     """
#     Middleware corrigé pour résoudre correctement le tenant
#     """
#
#     def __init__(self, get_response):
#         self.get_response = get_response
#
#     def _from_host(self, host):
#         m = SUBDOMAIN_RE.match((host or "").split(":")[0])
#         if m:
#             return m.group("tenant")
#         return None
#
#     def __call__(self, request):
#         tenant_id = None
#
#         # 1) Header X-Tenant-Id (priorité haute)
#         tenant_id = request.META.get("HTTP_X_TENANT_ID")
#
#         # 2) Session
#         if not tenant_id:
#             tenant_id = request.session.get("tenant_id") or request.session.get(
#                 getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
#             )
#
#         # 3) Host/sous-domaine
#         if not tenant_id:
#             tenant_id = self._from_host(request.get_host())
#
#         # 4) Token JWT (si présent)
#         if not tenant_id:
#             tenant_id = self._tenant_from_bearer(request)
#
#         # 5) Fallback
#         if not tenant_id:
#             tenant_id = getattr(settings, "DEFAULT_TENANT", None)
#
#         # Résolution du tenant
#         tenant_obj = resolve_tenant(tenant_id)
#         request.tenant = tenant_obj
#         request.tenant_id = tenant_id
#
#         # Injection du header pour les vues API
#         if tenant_id and "HTTP_X_TENANT_ID" not in request.META:
#             request.META["HTTP_X_TENANT_ID"] = str(tenant_id)
#
#         return self.get_response(request)
#
#     def _tenant_from_bearer(self, request):
#         auth = request.META.get("HTTP_AUTHORIZATION", "")
#         if not auth.startswith("Bearer "):
#             return None
#         token = auth.split(" ", 1)[1].strip()
#         try:
#             payload = jwt.decode(token, options={"verify_signature": False})
#             # 1) claim direct
#             if "tenant" in payload:
#                 return payload["tenant"]
#             # 2) claim tenant_id
#             if "tenant_id" in payload:
#                 return payload["tenant_id"]
#             # 3) groupe/role style "tenant : acme"
#             roles = (payload.get("realm_access", {}) or {}).get("roles", [])
#             for r in roles:
#                 if r.startswith("tenant:"):
#                     return r.split(":", 1)[1]
#         except Exception:
#             return None
#         return None
#
#
# class TenantResolutionMiddleware:
#     """
#     - Résout request. Tenant (instance) et request.tenant_id (UUID str)
#     - Range tenant_id en session pour cohérence
#     - Bloque les endpoints /api/* si aucun tenant n’est trouvé
#     """
#     def __init__(self, get_response: Callable):
#         self.get_response = get_response
#
#     def __call__(self, request):
#         tenant = get_tenant_from_request(request)
#         if tenant:
#             request.tenant = tenant
#             request.tenant_id = str(tenant.id)
#             if hasattr(request, "session"):
#                 request.session["tenant_id"] = request.tenant_id
#         else:
#             request.tenant = None
#             request.tenant_id = None
#
#         if (request.path.startswith("/api/") or "application/json" in (request.headers.get("Accept") or "")) and not request.tenant:
#             return JsonResponse({"detail": "Tenant introuvable", "code": "tenant_not_found"}, status=403)
#
#         return self.get_response(request)
#
#
# class CurrentTenant:
#     slug: str | None = None
#     obj: Tenant | None = None
#
#
# class TenantSessionMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response
#         self.key = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
#
#     def __call__(self, request):
#         request.tenant_id = request.session.get(self.key)
#         return self.get_response(request)
#
#
# #
# #
# TENANT_HEADER = "HTTP_X_TENANT_ID"
# TENANT_SESSION_KEY = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
# TENANT_REGEX = getattr(settings, "TENANT_SUBDOMAIN_REGEX", r"^(?P<tenant>[a-z0-9-]+)\.")
#
#
# #
# #
# def _tenant_from_host(host: str) -> str | None:
#     # ex: acme.rh.lyneerp.com -> "acme"
#     m = re.match(TENANT_REGEX, host, re.IGNORECASE)
#     if m:
#         return m.group("tenant")
#     return None
#
#
# def _tenant_from_bearer(request) -> str | None:
#     auth = request.META.get("HTTP_AUTHORIZATION", "")
#     if not auth.startswith("Bearer "):
#         return None
#     token = auth.split(" ", 1)[1].strip()
#     try:
#         # On ne valide pas la signature ici (déjà fait par la vue/API si nécessaire),
#         # on lit juste le claim pour orienter le tenant.
#         payload = jwt.decode(token, options={"verify_signature": False})
#         # 1) claim direct
#         if "tenant" in payload:
#             return payload["tenant"]
#         # 2) groupe/role style "tenant : acme"
#         roles = (payload.get("realm_access", {}) or {}).get("roles", [])
#         for r in roles:
#             if r.startswith("tenant:"):
#                 return r.split(":", 1)[1]
#     except Exception:
#         return None
#     return None
#
#
# class TenantMiddleware(MiddlewareMixin):
#     def process_request(self, request):
#         # 1) Host
#         host = request.get_host().split(":")[0]
#         tenant = _tenant_from_host(host)
#
#         # 2) Header (si proxy/traefik/kong ajoute X-Tenant-Id)
#         if not tenant:
#             tenant = request.META.get(TENANT_HEADER)
#
#         # 3) Token Bearer
#         if not tenant:
#             tenant = _tenant_from_bearer(request)
#
#         # 4) Fallback : éventuellement une valeur par défaut (ex : "default")
#         if not tenant:
#             tenant = getattr(settings, "DEFAULT_TENANT", None)
#
#         request.tenant_id = tenant
#         # Si tu veux encore garder une session, ok, mais pas obligatoire :
#         if hasattr(request, "session"):
#             request.session[TENANT_SESSION_KEY] = tenant
#
#
# SUBDOMAIN_RE = re.compile(getattr(
#     settings,
#     "TENANT_SUBDOMAIN_REGEX",
#     r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"
# ), re.I)
#
#
# class RequestTenantMiddleware:
#     """
#     - Déduit request. tenant (obj Tenant) à partir de la session ou du sous-domaine
#     - S'assure que 'HTTP_X_TENANT_ID' est présent pour les vues DRF/permissions
#     """
#
#     def __init__(self, get_response):
#         self.get_response = get_response
#
#     def _from_host(self, host):
#         m = SUBDOMAIN_RE.match((host or "").split(":")[0])
#         if m:
#             return m.group("tenant")
#         return None
#
#     def __call__(self, request):
#         # 1) session / cookie
#         tid = request.session.get("tenant_id") or request.session.get(
#             getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
#         )
#
#         # 2) host
#         if not tid:
#             tid = self._from_host(request.get_host())
#
#         tenant_obj = resolve_tenant(tid)
#         request.tenant = tenant_obj  # peut-être None, c'est OK
#
#         # 3) Injecte X-Tenant-Id si manquant
#         if tenant_obj and "HTTP_X_TENANT_ID" not in request.META:
#             request.META["HTTP_X_TENANT_ID"] = str(tenant_obj.id)
#
#         return self.get_response(request)
