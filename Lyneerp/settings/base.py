"""
Settings communs à tous les environnements LYNEERP.

Charge automatiquement le fichier ``.env`` du projet pour le développement
local, mais en production on s'attend à ce que les variables soient
injectées via le runtime (Docker / systemd / k8s).

Les overrides spécifiques sont dans :
- ``dev.py``  : développement local
- ``prod.py`` : production durcie
- ``test.py`` : exécution des tests
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Charge le .env uniquement s'il existe (le fichier ne doit pas être versionné).
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}


def env_list(key: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(key, "")
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Sécurité
# --------------------------------------------------------------------------- #
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-base-key-only-for-bootstrap-replace-me",
)
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Cookies sains par défaut (les overrides prod activent SECURE).
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # tableau de bord lit le token via cookie en JS
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------------------------------- #
# Apps installées
# --------------------------------------------------------------------------- #
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "storages",
    "mozilla_django_oidc",
]

LOCAL_APPS = [
    "tenants",
    "hr",
    "finance",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --------------------------------------------------------------------------- #
# Middlewares
# --------------------------------------------------------------------------- #
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # ❶ Notre middleware tenant doit être placé APRÈS l'auth pour pouvoir
    #     vérifier la cohérence user ↔ tenant.
    "tenants.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --------------------------------------------------------------------------- #
# URLs / WSGI / ASGI
# --------------------------------------------------------------------------- #
ROOT_URLCONF = "Lyneerp.urls"
WSGI_APPLICATION = "Lyneerp.wsgi.application"
ASGI_APPLICATION = "Lyneerp.asgi.application"

# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tenants.context_processors.current_tenant",
            ],
        },
    },
]

# --------------------------------------------------------------------------- #
# Base de données
# --------------------------------------------------------------------------- #
DB_ENGINE = os.getenv("DB_ENGINE", "postgres").lower()

if DB_ENGINE in {"postgres", "postgresql", "psql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "lyneerp"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "OPTIONS": {
                "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 5),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("DB_NAME", "db.sqlite3"),
        }
    }

# --------------------------------------------------------------------------- #
# Authentication / passwords
# --------------------------------------------------------------------------- #
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Backend custom : tenant + Keycloak OIDC, fallback model par défaut.
AUTHENTICATION_BACKENDS = [
    "hr.oidc_backend.KeycloakOIDCBackend",
    "tenants.auth_backends.TenantModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = os.getenv("LOGIN_URL", "/login/")
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL", "/")
LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL", "/login/")

# --------------------------------------------------------------------------- #
# I18n / TZ
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "fr-fr")
TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Abidjan")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Static / Media (WhiteNoise + S3/MinIO)
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Bascule sur S3/MinIO si AWS_STORAGE_BUCKET_NAME défini.
AWS_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("S3_BUCKET")
AWS_S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT")
AWS_S3_REGION_NAME = os.getenv("S3_REGION", "us-east-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "path"
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_S3_FILE_OVERWRITE = False

S3_PUBLIC_HOST = os.getenv("S3_PUBLIC_HOST", "")
S3_PUBLIC_SCHEME = os.getenv("S3_PUBLIC_SCHEME", "https")
if S3_PUBLIC_HOST:
    AWS_S3_CUSTOM_DOMAIN = S3_PUBLIC_HOST

if AWS_STORAGE_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
else:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Cache (Redis si dispo, sinon LocMem)
# --------------------------------------------------------------------------- #
REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,  # cache best-effort
            },
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "lyneerp-default",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# --------------------------------------------------------------------------- #
# Celery
# --------------------------------------------------------------------------- #
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", REDIS_URL or "redis://127.0.0.1:6379/0"
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND", REDIS_URL or "redis://127.0.0.1:6379/0"
)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 60 * 5)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 60 * 4)

# --------------------------------------------------------------------------- #
# Django REST Framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "hr.auth.KeycloakJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": env_int("DRF_PAGE_SIZE", 25),
    "EXCEPTION_HANDLER": "Lyneerp.exception_handler.lyneerp_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "LYNEERP API",
    "DESCRIPTION": (
        "API de la plateforme LYNEERP : RH, Finance, Tenants, Licences, "
        "Workflows métier."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
}

# --------------------------------------------------------------------------- #
# Multi-tenant
# --------------------------------------------------------------------------- #
TENANT_SESSION_KEY = "current_tenant"
TENANT_SUBDOMAIN_REGEX = os.getenv(
    "TENANT_SUBDOMAIN_REGEX",
    r"^(?P<tenant>[a-z0-9-]+)\.(?:rh\.)?lyneerp\.com$",
)
DEFAULT_TENANT = os.getenv("DEFAULT_TENANT") or None
LICENSE_ENFORCEMENT = env_bool("LICENSE_ENFORCEMENT", False)

# --------------------------------------------------------------------------- #
# Keycloak / OIDC
# --------------------------------------------------------------------------- #
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "lyneerp")
KEYCLOAK_ISSUER = os.getenv(
    "KEYCLOAK_ISSUER",
    f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}" if KEYCLOAK_BASE_URL else "",
)
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "rh-core")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "rh-core")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "") or None
KEYCLOAK_JWKS_URL = os.getenv(
    "KEYCLOAK_JWKS_URL",
    f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
    if KEYCLOAK_ISSUER
    else "",
)
KEYCLOAK_USE_REALM_PER_TENANT = env_bool("KEYCLOAK_USE_REALM_PER_TENANT", False)

# Mapping optionnel tenant slug -> realm Keycloak (override via JSON env si besoin)
TENANT_REALMS = {}

# mozilla-django-oidc : on dérive depuis les variables Keycloak.
OIDC_RP_CLIENT_ID = KEYCLOAK_CLIENT_ID
OIDC_RP_CLIENT_SECRET = KEYCLOAK_CLIENT_SECRET
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_FETCH_USERINFO = False
OIDC_STORE_ID_TOKEN = True
OIDC_STORE_ACCESS_TOKEN = True
OIDC_TIMEOUT = env_int("OIDC_TIMEOUT", 10)
OIDC_SESSION_KEY = "oidc_user"

if KEYCLOAK_ISSUER:
    OIDC_OP_ISSUER = KEYCLOAK_ISSUER
    OIDC_OP_AUTHORIZATION_ENDPOINT = (
        f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth"
    )
    OIDC_OP_TOKEN_ENDPOINT = os.getenv(
        "OIDC_OP_TOKEN_ENDPOINT",
        f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token",
    )
    OIDC_OP_USER_ENDPOINT = os.getenv(
        "OIDC_OP_USER_ENDPOINT",
        f"{KEYCLOAK_ISSUER}/protocol/openid-connect/userinfo",
    )
    OIDC_OP_JWKS_ENDPOINT = KEYCLOAK_JWKS_URL
    OIDC_OP_DISCOVERY_ENDPOINT = (
        f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration"
    )

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "")  # ex: /var/log/lyneerp/app.log

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"ts":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","msg":"%(message)s"}'
            ),
        },
        "console": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "console",
        },
        **(
            {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": LOG_FILE,
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 5,
                    "level": LOG_LEVEL,
                    "formatter": "json",
                }
            }
            if LOG_FILE
            else {}
        ),
    },
    "root": {
        "handlers": ["console"] + (["file"] if LOG_FILE else []),
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "Lyneerp": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "tenants": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "hr": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "finance": {
            "handlers": ["console"] + (["file"] if LOG_FILE else []),
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
