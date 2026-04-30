"""
Views d'authentification multi-tenant pour LYNEERP.

- ``keycloak_direct_login`` : flow ``Direct Access Grants`` (resource owner
  password). Réservé aux clients internes ou aux scripts de migration. Le flow
  recommandé reste l'Authorization Code (PKCE) via mozilla-django-oidc.

- ``logout_view`` : déconnexion locale + propagation Keycloak (logout SSO).

Sécurité :
- Protection CSRF (plus de ``csrf_exempt``)
- Validation TenantUser actif avant de poser la session locale
- Pas de stockage des tokens Keycloak côté client
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login as dj_login, logout as dj_logout
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from jose import jwt as jose_jwt

from hr.auth_utils import ensure_seat_for_user
from tenants.models import Tenant, TenantUser
from tenants.utils import resolve_tenant

logger = logging.getLogger(__name__)
User = get_user_model()

TENANT_COOKIE_KEY = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _subdomain_re() -> re.Pattern[str]:
    return re.compile(
        getattr(
            settings,
            "TENANT_SUBDOMAIN_REGEX",
            r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$",
        ),
        re.IGNORECASE,
    )


def _extract_next(request: HttpRequest, body: dict) -> str:
    nxt = request.GET.get("next") or request.POST.get("next") or body.get("next")
    return nxt or getattr(settings, "LOGIN_REDIRECT_URL", "/")


def _infer_tenant(request: HttpRequest, provided: Optional[str]) -> Optional[str]:
    """
    Détermine l'identifiant tenant pour la requête de login. Ordre :
    payload → header → session → sous-domaine → DEFAULT_TENANT.
    """
    if provided:
        return str(provided).strip()
    hdr = request.headers.get("X-Tenant-Id")
    if hdr:
        return hdr.strip()
    if hasattr(request, "session"):
        ses = request.session.get("tenant_id") or request.session.get(TENANT_COOKIE_KEY)
        if ses:
            return str(ses).strip()
    host = request.get_host().split(":", 1)[0]
    match = _subdomain_re().match(host)
    if match:
        return match.group("tenant")
    return getattr(settings, "DEFAULT_TENANT", None)


def _realm_for_tenant(tenant_obj: Optional[Tenant]) -> str:
    """
    Mapping tenant → realm.
    """
    realms = getattr(settings, "TENANT_REALMS", {}) or {}
    if (
        getattr(settings, "KEYCLOAK_USE_REALM_PER_TENANT", False)
        and tenant_obj is not None
    ):
        realm = realms.get(tenant_obj.slug)
        if realm:
            return realm
    return getattr(settings, "KEYCLOAK_REALM", "lyneerp")


def _token_endpoint(base_url: str, realm: str) -> str:
    return f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token"


def _logout_endpoint(base_url: str, realm: str) -> str:
    return f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/logout"


def _parse_body(request: HttpRequest) -> dict:
    if request.POST:
        return request.POST.dict()
    try:
        return json.loads(request.body or "{}")
    except Exception:  # noqa: BLE001
        return {}


# --------------------------------------------------------------------------- #
# Vues
# --------------------------------------------------------------------------- #
@require_POST
@csrf_protect
def keycloak_direct_login(request: HttpRequest):
    """
    Login serveur via password grant Keycloak.

    À utiliser pour des clients qui ne peuvent pas faire d'Authorization Code.
    En production, **préférer** ``/oidc/authenticate/`` (mozilla-django-oidc).
    """
    data = _parse_body(request)
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    tenant_identifier = _infer_tenant(request, data.get("tenant_id"))
    next_url = _extract_next(request, data)

    if not username or not password:
        return JsonResponse(
            {"detail": "username et password requis", "code": "missing_credentials"},
            status=400,
        )

    tenant_obj = resolve_tenant(tenant_identifier)
    if tenant_obj is None:
        return JsonResponse(
            {
                "detail": "Organisation introuvable.",
                "code": "tenant_not_found",
                "tenant_attempted": tenant_identifier,
            },
            status=400,
        )
    if not tenant_obj.is_active:
        return JsonResponse(
            {"detail": "Organisation désactivée.", "code": "tenant_inactive"},
            status=403,
        )

    realm = _realm_for_tenant(tenant_obj)
    kc_base = getattr(settings, "KEYCLOAK_BASE_URL", "").rstrip("/")
    if not kc_base:
        logger.error("KEYCLOAK_BASE_URL non configuré.")
        return JsonResponse(
            {"detail": "Configuration SSO manquante.", "code": "sso_misconfigured"},
            status=500,
        )

    form = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }
    if getattr(settings, "KEYCLOAK_CLIENT_SECRET", None):
        form["client_secret"] = settings.KEYCLOAK_CLIENT_SECRET

    try:
        resp = requests.post(_token_endpoint(kc_base, realm), data=form, timeout=12)
    except requests.RequestException as exc:
        logger.warning("Keycloak injoignable : %s", exc)
        return JsonResponse(
            {"detail": "SSO injoignable.", "code": "sso_unreachable"},
            status=502,
        )

    if resp.status_code != 200:
        logger.info(
            "Auth Keycloak refusée user=%s tenant=%s status=%s",
            username,
            tenant_obj.slug,
            resp.status_code,
        )
        return JsonResponse(
            {"detail": "Authentification refusée.", "code": "invalid_credentials"},
            status=401,
        )

    tokens = resp.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    if not access_token:
        return JsonResponse(
            {"detail": "Token manquant.", "code": "sso_invalid_response"},
            status=502,
        )

    # Lecture des claims (signature non vérifiée ici — vérification déjà faite par KC)
    claims = {}
    try:
        if id_token:
            claims = jose_jwt.get_unverified_claims(id_token)
    except Exception:  # noqa: BLE001
        claims = {}
    access_claims = {}
    try:
        access_claims = jose_jwt.get_unverified_claims(access_token)
    except Exception:  # noqa: BLE001
        pass

    email = claims.get("email") or claims.get("preferred_username") or username
    first = claims.get("given_name") or ""
    last = claims.get("family_name") or ""

    user, _created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "first_name": first, "last_name": last},
    )
    update_fields = []
    if email and user.email != email:
        user.email = email
        update_fields.append("email")
    if first and user.first_name != first:
        user.first_name = first
        update_fields.append("first_name")
    if last and user.last_name != last:
        user.last_name = last
        update_fields.append("last_name")
    if update_fields:
        user.save(update_fields=update_fields)

    # ✅ Vérifie l'appartenance au tenant — refus si pas d'accès.
    if not user.is_superuser:
        membership = (
            TenantUser.objects
            .filter(user=user, tenant=tenant_obj, is_active=True)
            .first()
        )
        if membership is None:
            logger.info(
                "Refus tenant : user=%s n'appartient pas à tenant=%s",
                user.pk,
                tenant_obj.slug,
            )
            return JsonResponse(
                {
                    "detail": "Vous n'avez pas accès à cette organisation.",
                    "code": "tenant_access_denied",
                },
                status=403,
            )

    # Pose la session Django (cookie httponly).
    request.session["tenant_id"] = str(tenant_obj.id)
    request.session[TENANT_COOKIE_KEY] = str(tenant_obj.id)
    request.session[settings.OIDC_SESSION_KEY] = {
        "realm": realm,
        "id_token": id_token,
        "preferred_username": claims.get("preferred_username", username),
        "email": email,
        "roles": (access_claims.get("realm_access", {}) or {}).get("roles", []),
    }
    request.session.modified = True

    user.backend = "django.contrib.auth.backends.ModelBackend"
    dj_login(request, user)

    sub = access_claims.get("sub") or claims.get("sub")
    if sub:
        try:
            ensure_seat_for_user(tenant_obj, "rh", sub, user.email)
        except Exception:  # noqa: BLE001
            logger.exception("ensure_seat_for_user failed for user=%s", user.pk)

    return JsonResponse(
        {
            "ok": True,
            "redirect": next_url,
            "tenant": {"id": str(tenant_obj.id), "slug": tenant_obj.slug},
            "user": {"username": user.username, "email": user.email},
        }
    )


def logout_view(request: HttpRequest):
    """
    Déconnecte la session Django et (si possible) la session Keycloak.
    """
    kc = request.session.get(settings.OIDC_SESSION_KEY) or {}
    realm = kc.get("realm") or getattr(settings, "KEYCLOAK_REALM", "lyneerp")
    id_token = kc.get("id_token")

    dj_logout(request)

    kc_base = getattr(settings, "KEYCLOAK_BASE_URL", "").rstrip("/")
    post_logout = (
        request.GET.get("post_logout_redirect_uri")
        or getattr(settings, "LOGOUT_REDIRECT_URL", "/login/")
    )
    if realm and id_token and kc_base:
        url = (
            f"{_logout_endpoint(kc_base, realm)}"
            f"?post_logout_redirect_uri={request.build_absolute_uri(post_logout)}"
            f"&id_token_hint={id_token}"
        )
        return redirect(url)
    return redirect(post_logout)
