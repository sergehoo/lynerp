# hr/oidc_backend.py
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """Backend OIDC custom pour Keycloak : pas d'appel /userinfo."""

    def get_userinfo(self, access_token, id_token, payload):
        # Ne plus appeler /userinfo : on se base sur l'ID Token
        return payload

    def get_username(self, claims):
        return (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("sub")
        )

    def create_user(self, claims):
        user = super().create_user(claims)
        user.email = claims.get("email", "")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()
        return user

    def update_user(self, user, claims):
        user.email = claims.get("email", "")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()
        return user