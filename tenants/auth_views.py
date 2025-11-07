# hr/auth_views.py
from __future__ import annotations

import json
import re
import requests
from typing import Optional

from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # ⚠️ garde seulement si tu n'envoies pas le CSRF
from django.contrib.auth import get_user_model, login as dj_login, logout as dj_logout

from jose import jwt  # python-jose

from hr.auth_utils import ensure_seat_for_user
from tenants.models import Tenant
from tenants.utils import resolve_tenant

User = get_user_model()

TENANT_COOKIE_KEY = getattr(settings, "TENANT_SESSION_KEY", "current_tenant")
SUBDOMAIN_RE = re.compile(getattr(settings, "TENANT_SUBDOMAIN_REGEX",
                                  r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"),
                          re.I)


def _extract_next(request: HttpRequest) -> str:
    """Récupère la cible de redirection finale."""
    nxt = request.GET.get("next") or request.POST.get("next")
    if not nxt:
        try:
            body = json.loads(request.body or "{}")
            nxt = body.get("next")
        except Exception:
            pass
    return nxt or getattr(settings, "LOGIN_REDIRECT_URL", "/")


def _infer_tenant(request: HttpRequest, provided_tenant: Optional[str]) -> Optional[str]:
    """
    Déduit le tenant dans l'ordre :
      1) champ fourni (JSON/form)
      2) header X-Tenant-Id
      3) session/cookie
      4) sous-domaine (rh.<tenant>.lyneerp.com ou <tenant>.lyneerp.com selon le REGEX)
    """
    if provided_tenant:
        return provided_tenant.strip()

    hdr = request.headers.get("X-Tenant-Id")
    if hdr:
        return hdr.strip()

    ses = request.session.get("tenant_id") or request.session.get(TENANT_COOKIE_KEY)
    if ses:
        return str(ses).strip()

    host = request.get_host().split(":")[0]
    m = SUBDOMAIN_RE.match(host)
    if m:
        return m.group("tenant")
    return getattr(settings, "DEFAULT_TENANT", None)


def _realm_for_tenant(tenant_id: Optional[str]) -> str:
    """
    Si KEYCLOAK_USE_REALM_PER_TENANT=True, mappe via TENANT_REALMS.
    Sinon, utilise le realm du projet (lyneerp).
    """
    if getattr(settings, "KEYCLOAK_USE_REALM_PER_TENANT", False):
        if tenant_id:
            realm = settings.TENANT_REALMS.get(tenant_id)
            if realm:
                return realm
        return "master"
    # un seul realm global
    return "lyneerp"


def _token_endpoint(base_url: str, realm: str) -> str:
    return f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token"


def _logout_endpoint(base_url: str, realm: str) -> str:
    return f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/logout"


def _parse_body(request: HttpRequest) -> dict:
    if request.POST:
        return request.POST.dict()
    try:
        return json.loads(request.body or "{}")
    except Exception:
        return {}


@require_POST
@csrf_exempt  # ✅ garde si tu postes depuis un JS public sans CSRF. Sinon remplace par @csrf_protect.
def keycloak_direct_login(request: HttpRequest):
    """
    Échange username/password contre un token Keycloak via 'password grant' (Direct Access Grants).
    ⚠️ Production : privilégie le flow Authorization Code ; ici, on garde pour cas d’usage spécifique.
    - tenant_id est optionnel : déduit automatiquement si absent.
    - respecte ? next=... pour la redirection finale.
    - crée/synchronise un user local (utile pour Django admin/permissions).
    """
    data = _parse_body(request)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    tenant_id = _infer_tenant(request, data.get("tenant_id"))
    next_url = _extract_next(request)

    if not username or not password:
        return JsonResponse({"detail": "username et password requis"}, status=400)

    realm = _realm_for_tenant(tenant_id)
    kc_base = getattr(settings, "KEYCLOAK_BASE_URL", "").rstrip("/")
    if not kc_base:
        return JsonResponse({"detail": "KEYCLOAK_BASE_URL manquant dans settings"}, status=500)

    token_url = _token_endpoint(kc_base, realm)

    form = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }
    if getattr(settings, "KEYCLOAK_CLIENT_SECRET", ""):
        form["client_secret"] = settings.KEYCLOAK_CLIENT_SECRET

    try:
        resp = requests.post(token_url, data=form, timeout=12)
    except requests.RequestException as e:
        return JsonResponse({"detail": f"Keycloak injoignable: {e}"}, status=502)

    if resp.status_code != 200:
        # renvoie le message d'erreur KC pour debug
        err = {}
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}
        return JsonResponse({"detail": "Authentification refusée", "kc_error": err}, status=401)

    tokens = resp.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    if not access_token:
        return JsonResponse({"detail": "access_token manquant"}, status=502)

    # Décodage 'non vérifié' pour récupérer les claims utiles (pas de validation ici)
    claims = {}
    try:
        if id_token:
            claims = jwt.get_unverified_claims(id_token)
    except Exception:
        claims = {}

    email = claims.get("email") or f"{username}@{realm}.local"
    first = claims.get("given_name") or username
    last = claims.get("family_name") or ""

    # Création/MAJ user local
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "first_name": first, "last_name": last},
    )
    changed = False
    if user.email != email:
        user.email = email; changed = True
    if user.first_name != first:
        user.first_name = first; changed = True
    if user.last_name != last:
        user.last_name = last; changed = True
    if changed:
        user.save(update_fields=["email", "first_name", "last_name"])

    # Session Django & contexte OIDC
    request.session["tenant_id"] = tenant_id or ""
    request.session[TENANT_COOKIE_KEY] = tenant_id or ""
    request.session[settings.OIDC_SESSION_KEY] = {
        "realm": realm,
        "access_token": access_token,
        "id_token": id_token,
        "preferred_username": claims.get("preferred_username", username),
        "email": email,
    }
    request.session.modified = True

    dj_login(request, user)
    tenant_obj = resolve_tenant(tenant_id)
    if tenant_obj:
        # sub/email pour siège
        access_claims = jwt.get_unverified_claims(access_token) if access_token else {}
        sub = access_claims.get("sub")
        ensure_seat_for_user(tenant_obj, "rh", sub, user.email)
    return JsonResponse({"ok": True, "redirect": next_url})


def logout_view(request: HttpRequest):
    """
    Déconnecte la session Django et (optionnel) la session Keycloak.
    """
    kc = request.session.get(settings.OIDC_SESSION_KEY) or {}
    realm = kc.get("realm")
    id_token = kc.get("id_token")

    # purge session Django
    dj_logout(request)

    # logout SSO Keycloak si possible
    kc_base = getattr(settings, "KEYCLOAK_BASE_URL", "").rstrip("/")
    post_logout = request.GET.get("post_logout_redirect_uri") or "/login/"
    if realm and id_token and kc_base:
        end_sess = _logout_endpoint(kc_base, realm)
        url = f"{end_sess}?post_logout_redirect_uri={request.build_absolute_uri(post_logout)}&id_token_hint={id_token}"
        return redirect(url)

    return redirect(post_logout)