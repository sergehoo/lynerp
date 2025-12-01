# settings/prod.py
import os
from .base import *

DEBUG = True
SECURE_SSL_REDIRECT = True
# pour le retour en HTTPS strict
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


CSRF_TRUSTED_ORIGINS = [
    "http://www.lynerp.com",
    "https://rh.lynerp.com",
    "http://rh.lynerp.com",
    "http://lynerp.com",
    "https://lynerp.com",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

# AUTHENTICATION_BACKENDS = [
#     "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
#     "django.contrib.auth.backends.ModelBackend",
# ]
LOGIN_URL = "/oidc/authenticate/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
# Optionnel : nom du cookie “tenant”
TENANT_SESSION_KEY = "current_tenant"
REMEMBER_ME_SESSION_AGE = 60 * 60 * 24 * 30  # 30 jours
SESSION_COOKIE_AGE = 60 * 60 * 2  # 2h (si pas remember me)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # expir. à la fermeture (par défaut)


KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "https://sso.lyneerp.com")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "rh-core")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")  # vide si client public
KEYCLOAK_USE_REALM_PER_TENANT = True  # ou False si un seul realm global

# Mapping tenant -> realm (exemple)
TENANT_REALMS = {
    "acme": "lyneerp",
    "demo": "lyneerp",
}
OIDC_SESSION_KEY = "oidc_user"
# Optionnel
TENANT_SUBDOMAIN_REGEX = r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"
DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", None)
# Où stocker les infos utilisateur dans la session

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Sufficient pour un retour GET top-level depuis IdP
SESSION_COOKIE_SAMESITE = "Lax"

# Recommandé si tu utilises des sous-domaines
SESSION_COOKIE_DOMAIN = ".lyneerp.com"



# --- OIDC / Keycloak ---


# Issuer public (ce que verront les navigateurs et ce qui est dans les tokens)
OIDC_OP_ISSUER = "https://sso.lyneerp.com/realms/lyneerp"

# (Optionnel) Discovery – pas obligatoire mais utile
OIDC_OP_DISCOVERY_ENDPOINT = (
    "https://sso.lyneerp.com/realms/lyneerp/.well-known/openid-configuration"
)

# Endpoints publics OIDC (tous en HTTPS)
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://sso.lyneerp.com/realms/lyneerp/protocol/openid-connect/auth"
# Endpoints appelés PAR LE BACKEND (via le réseau Docker)
OIDC_OP_TOKEN_ENDPOINT = (
    "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/token"
)
OIDC_OP_USER_ENDPOINT = (
    "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/userinfo"
)

OIDC_OP_JWKS_ENDPOINT = (
    "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/certs"
)

KEYCLOAK_ISSUER = "https://sso.lyneerp.com/realms/lyneerp"
KEYCLOAK_AUDIENCE = "rh-core"
KEYCLOAK_JWKS_URL = "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/certs"
# Client OIDC (Keycloak)
OIDC_RP_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "rh-core")
# OIDC_RP_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
OIDC_RP_CLIENT_SECRET = None
OIDC_FETCH_USERINFO = False
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_STORE_ID_TOKEN = True
OIDC_STORE_ACCESS_TOKEN = True
OIDC_TIMEOUT = 10



LICENSE_ENFORCEMENT = False
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
    }
}


# # settings/prod.py
# import os
# from .base import *
#
# DEBUG = True
# SECURE_SSL_REDIRECT = False
# # pour le retour en HTTPS strict
# USE_X_FORWARDED_HOST = True
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
#
# CSRF_TRUSTED_ORIGINS = [
#     "http://www.lynerp.com",
#     "https://rh.lynerp.com",
#     "http://rh.lynerp.com",
#     "http://lynerp.com",
#     "https://lynerp.com",
# ]
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("DB_NAME"),
#         "USER": os.getenv("DB_USER"),
#         "PASSWORD": os.getenv("DB_PASSWORD"),
#         "HOST": os.getenv("DB_HOST"),
#         "PORT": os.getenv("DB_PORT"),
#     }
# }
#
# AUTHENTICATION_BACKENDS = [
#     "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
#     "django.contrib.auth.backends.ModelBackend",
# ]
# LOGIN_URL = "/oidc/authenticate/"
# LOGIN_REDIRECT_URL = "/"
# LOGOUT_REDIRECT_URL = "/"
# # Optionnel : nom du cookie “tenant”
# TENANT_SESSION_KEY = "current_tenant"
# REMEMBER_ME_SESSION_AGE = 60 * 60 * 24 * 30  # 30 jours
# SESSION_COOKIE_AGE = 60 * 60 * 2  # 2h (si pas remember me)
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # expir. à la fermeture (par défaut)
#
#
# KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "https://sso.lyneerp.com")
# KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "rh-core")
# KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")  # vide si client public
# KEYCLOAK_USE_REALM_PER_TENANT = True  # ou False si un seul realm global
#
# # Mapping tenant -> realm (exemple)
# TENANT_REALMS = {
#     "acme": "lyneerp",
#     "demo": "lyneerp",
# }
# OIDC_SESSION_KEY = "oidc_user"
# # Optionnel
# TENANT_SUBDOMAIN_REGEX = r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$"
# DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", None)
# # Où stocker les infos utilisateur dans la session
#
# # Default primary key field type
# # https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
#
# USE_X_FORWARDED_HOST = True
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
#
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
#
# # Sufficient pour un retour GET top-level depuis IdP
# SESSION_COOKIE_SAMESITE = "Lax"
#
# # Recommandé si tu utilises des sous-domaines
# SESSION_COOKIE_DOMAIN = ".lyneerp.com"
#
# CSRF_TRUSTED_ORIGINS = ["https://rh.lyneerp.com", "https://*.lyneerp.com"]
#
#
# # --- Garde l'issuer et l'AUTH endpoint publics (utilisés par le navigateur) ---
# OIDC_OP_ISSUER = "https://sso.lyneerp.com/realms/lyneerp"
# OIDC_OP_AUTHORIZATION_ENDPOINT = f"{OIDC_OP_ISSUER}/protocol/openid-connect/auth"
#
# # --- Endpoints appelés côté serveur : utilise le DNS docker du service keycloak ---
# OIDC_OP_TOKEN_ENDPOINT= "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/token"
# OIDC_OP_JWKS_ENDPOINT = "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/certs"
# OIDC_OP_USER_ENDPOINT = "http://keycloak:8080/realms/lyneerp/protocol/openid-connect/userinfo"
#
# OIDC_RP_CLIENT_ID = "rh-core"                    # client type "Public" dans Keycloak
# OIDC_RP_CLIENT_SECRET = None                     # None pour client public
# OIDC_OP_ISSUER = "https://sso.lyneerp.com/realms/lyneerp"
#
# # Algorithme de signature attendu pour les ID tokens (Keycloak = RS256 par défaut)
# OIDC_RP_SIGN_ALGO = "RS256"
# # 1) Scopes demandés (sinon certains IdP ne renvoient pas email/username)
# OIDC_RP_SCOPES = "openid email profile"
#
# # 2) Timeout des appels OIDC (échange code->token)
# OIDC_TIMEOUT = 10
#
# # 3) (Optionnel) Stocker les tokens en session si tu en as besoin après login
# OIDC_STORE_ID_TOKEN = True
# OIDC_STORE_ACCESS_TOKEN = True
#
# LICENSE_ENFORCEMENT = False
#
# SESSION_ENGINE = "django.contrib.sessions.backends.cache"
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": "redis://redis:6379/1",
#     }
# }
