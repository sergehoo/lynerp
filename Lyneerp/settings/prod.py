"""
Settings de production durcis.

Toutes les valeurs sensibles sont attendues en variables d'environnement.
Ne JAMAIS activer DEBUG ici.
"""
from __future__ import annotations

import os
import sys

from .base import *  # noqa: F401,F403
from .base import env_bool, env_int, env_list

# --------------------------------------------------------------------------- #
# Garde-fous critiques
# --------------------------------------------------------------------------- #
DEBUG = False

if not os.getenv("DJANGO_SECRET_KEY"):
    raise RuntimeError(
        "DJANGO_SECRET_KEY est obligatoire en production. "
        "Définissez la variable d'environnement avant de démarrer."
    )

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
    raise RuntimeError(
        "ALLOWED_HOSTS doit être renseigné en production via la variable d'env."
    )

# --------------------------------------------------------------------------- #
# HTTPS / cookies / proxy
# --------------------------------------------------------------------------- #
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # le front (Alpine) doit pouvoir lire le cookie CSRF
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 8)  # 8h max
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)
REMEMBER_ME_SESSION_AGE = env_int(
    "REMEMBER_ME_SESSION_AGE", 60 * 60 * 24 * 30
)

SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "") or None
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", SESSION_COOKIE_DOMAIN or "") or None

# CSRF_TRUSTED_ORIGINS hérite de base.py mais on impose au moins une valeur.
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith(".")],
)

# --------------------------------------------------------------------------- #
# Email (SMTP en prod)
# --------------------------------------------------------------------------- #
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@lyneerp.com")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# --------------------------------------------------------------------------- #
# Sécurité système
# --------------------------------------------------------------------------- #
# Empêche le démarrage si on est sur SQLite en prod (oubli de variable).
if "sqlite" in DATABASES["default"]["ENGINE"]:  # noqa: F405
    print(
        "[LYNEERP] WARN: configuration prod avec SQLite — refusé.",
        file=sys.stderr,
    )
    raise RuntimeError("DB_ENGINE=postgres requis en production.")
