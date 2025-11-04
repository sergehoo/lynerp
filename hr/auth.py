# hr/auth.py
import time
import json
from typing import Any, Dict, Optional

import requests
import jwt
from jwt import PyJWKClient, InvalidTokenError
from cachetools import TTLCache

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

# Cache du JWKS (évite un GET à chaque requête)
_JWKS_CACHE = TTLCache(maxsize=2, ttl=3600)  # 1h


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    client = _JWKS_CACHE.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url, cache_keys=True)
        _JWKS_CACHE[jwks_url] = client
    return client


def _get_auth_header_token(request) -> str:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth:
        raise exceptions.AuthenticationFailed("Missing Authorization header")
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise exceptions.AuthenticationFailed("Authorization must be Bearer <token>")
    return parts[1]


class KeycloakJWTAuthentication(BaseAuthentication):
    """
    Authentification JWT avec Keycloak (vérification via JWKS).
    Requiert dans settings :
      KEYCLOAK_ISSUER
      KEYCLOAK_AUDIENCE
      KEYCLOAK_JWKS_URL
    """

    def authenticate(self, request):
        try:
            token = _get_auth_header_token(request)
        except exceptions.AuthenticationFailed:
            return None  # pas d'auth → DRF tentera les autres classes; sinon IsAuthenticated échouera

        jwks_url = getattr(settings, "KEYCLOAK_JWKS_URL", None)
        issuer = getattr(settings, "KEYCLOAK_ISSUER", None)
        audience = getattr(settings, "KEYCLOAK_AUDIENCE", None)

        if not jwks_url or not issuer:
            raise exceptions.AuthenticationFailed("Keycloak configuration is missing")

        try:
            jwk_client = _get_jwks_client(jwks_url)
            signing_key = jwk_client.get_signing_key_from_jwt(token).key

            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": bool(audience),
                "verify_iss": True,
            }

            decoded = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "RS512", "ES256", "ES384"],
                audience=audience if audience else None,
                issuer=issuer,
                options=options,
            )

        except InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f"Invalid token: {e}") from e
        except Exception as e:
            raise exceptions.AuthenticationFailed(f"Token verification error: {e}") from e

        # Construit un "user" léger (optionnel: faire un modèle utilisateur ou lazy user)
        user = self.build_user_from_claims(decoded)
        # Attache le payload pour les permissions (HasRole, etc.)
        request.auth = decoded
        return (user, decoded)

    def build_user_from_claims(self, claims: Dict[str, Any]):
        """
        Retourne un objet user minimal compatible DRF : avec is_authenticated = True.
        Tu peux remplacer par un vrai modèle User si nécessaire.
        """

        class SimpleUser:
            def __init__(self, sub: str, email: Optional[str], name: Optional[str]):
                self.id = sub
                self.sub = sub
                self.email = email
                self.username = email or sub
                self.full_name = name
                self.is_active = True
                self.is_authenticated = True

        sub = claims.get("sub")
        email = claims.get("email") or claims.get("preferred_username")
        name = claims.get("name")
        return SimpleUser(sub, email, name)
