# auth/keycloak.py
import json, requests, jwt
from django.core.cache import cache
from rest_framework import authentication, exceptions
from django.conf import settings

KC_ISSUER = getattr(settings, "KEYCLOAK_ISSUER", "https://sso.lyneerp.com/realms/lyneerp")
KC_AUDIENCE = getattr(settings, "KEYCLOAK_AUDIENCE", "rh-core")
KC_JWKS_URL = f"{KC_ISSUER}/protocol/openid-connect/certs"

def _get_jwks():
  jwks = cache.get("kc_jwks")
  if not jwks:
    jwks = requests.get(KC_JWKS_URL, timeout=5).json()
    cache.set("kc_jwks", jwks, 3600)
  return jwks

class KeycloakJWTAuthentication(authentication.BaseAuthentication):
  def authenticate(self, request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
      return None
    token = auth.split(" ", 1)[1].strip()
    jwks = _get_jwks()
    try:
      unverified = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
      raise exceptions.AuthenticationFailed(f"JWT header error: {e}")

    key = next((k for k in jwks.get("keys", []) if k.get("kid") == unverified.get("kid")), None)
    if not key:
      raise exceptions.AuthenticationFailed("Invalid kid")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    try:
      payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=KC_AUDIENCE,
        issuer=KC_ISSUER,
        options={"require": ["exp", "iat", "iss", "aud"]},
      )
    except jwt.PyJWTError as e:
      raise exceptions.AuthenticationFailed(str(e))

    # petit user proxy
    user = type("KCUser", (), {
      "is_authenticated": True,
      "username": payload.get("preferred_username") or payload.get("sub"),
      "email": payload.get("email"),
      "oidc": payload,
    })
    request.oidc = payload
    return (user, None)