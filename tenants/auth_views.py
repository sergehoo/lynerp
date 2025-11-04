# hr/auth_views.py
import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # ou mieux: utilise le token CSRF
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from jose import jwt  # pip install python-jose
from django.contrib.auth import logout as dj_logout

User = get_user_model()

def _realm_for_tenant(tenant_id: str) -> str:
    if settings.KEYCLOAK_USE_REALM_PER_TENANT:
        return settings.TENANT_REALMS.get(tenant_id) or "master"
    return "lyneerp"  # realm par défaut

@require_POST
@csrf_exempt  # si tu restes en POST JS simple; sinon utilise {% csrf_token %} + fetch avec header X-CSRFToken
def keycloak_direct_login(request):
    data = request.POST or request.body
    if hasattr(request, "body") and not request.POST:
        import json
        data = json.loads(request.body or "{}")

    tenant_id = (data.get("tenant_id") or "").strip()
    username  = (data.get("username")  or "").strip()
    password  = (data.get("password")  or "").strip()

    if not (tenant_id and username and password):
        return JsonResponse({"detail": "Champs manquants."}, status=400)

    realm = _realm_for_tenant(tenant_id)
    token_url = f"{settings.KEYCLOAK_BASE_URL}/realms/{realm}/protocol/openid-connect/token"

    form = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }
    auth = None
    # Si client confidential, ajoute client_secret
    if settings.KEYCLOAK_CLIENT_SECRET:
        form["client_secret"] = settings.KEYCLOAK_CLIENT_SECRET

    try:
        resp = requests.post(token_url, data=form, timeout=10)
    except requests.RequestException as e:
        return JsonResponse({"detail": f"Keycloak injoignable: {e}"}, status=502)

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = {"error": resp.text}
        return JsonResponse({"detail": "Authentification refusée", "kc_error": err}, status=401)

    tokens = resp.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    if not access_token:
        return JsonResponse({"detail": "Token manquant"}, status=502)

    # Décoder l’ID token (si présent) pour infos profil
    user_info = {}
    try:
        if id_token:
            # Keycloak signe en général en RS256 – on peut ignorer la vérif de signature ici
            # et se limiter à l’accès via introspection plus tard, ou récupérer la jwks.
            user_info = jwt.get_unverified_claims(id_token)
    except Exception:
        user_info = {}

    email = user_info.get("email") or f"{username}@{realm}.local"
    first = user_info.get("given_name") or username
    last  = user_info.get("family_name") or ""

    # Créer/synchroniser un utilisateur local (facultatif mais pratique pour permissions Django)
    user, _ = User.objects.get_or_create(username=username, defaults={"email": email, "first_name": first, "last_name": last})
    # Tu peux aussi mettre à jour les champs au besoin
    user.email = email
    user.first_name = first
    user.last_name = last
    user.save(update_fields=["email", "first_name", "last_name"])

    # Stocker contexte OIDC en session
    request.session["tenant_id"] = tenant_id
    request.session[settings.OIDC_SESSION_KEY] = {
        "realm": realm,
        "access_token": access_token,
        "id_token": id_token,
        "preferred_username": user_info.get("preferred_username", username),
        "email": email,
    }
    request.session.modified = True

    # Auth Django (session)
    login(request, user)

    return JsonResponse({"ok": True, "redirect": settings.LOGIN_REDIRECT_URL})

def logout_view(request):
    kc = request.session.get(settings.OIDC_SESSION_KEY) or {}
    realm = kc.get("realm")
    id_token = kc.get("id_token")

    # Nettoie la session Django
    dj_logout(request)

    # (Optionnel) Redirige vers end-session pour fermer la session SSO
    if realm and id_token:
        end_sess = f"{settings.KEYCLOAK_BASE_URL}/realms/{realm}/protocol/openid-connect/logout"
        # Tu peux faire un GET avec id_token_hint et post_logout_redirect_uri
        return redirect(end_sess + "?post_logout_redirect_uri=" + request.build_absolute_uri("/login/"))
    return redirect("/login/")