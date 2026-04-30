"""
Settings de développement local.

Active automatiquement DEBUG, ouvre ALLOWED_HOSTS, n'impose pas SSL.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK, env_bool

DEBUG = True
ALLOWED_HOSTS = ["*"]

# En dev on accepte aussi BrowsableAPI pour faciliter le debug DRF.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# Outils dev : django-debug-toolbar si présent.
if env_bool("ENABLE_DEBUG_TOOLBAR", False):
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS = list(INSTALLED_APPS) + ["debug_toolbar"]  # noqa: F405
        MIDDLEWARE = (  # noqa: F405
            ["debug_toolbar.middleware.DebugToolbarMiddleware"] + list(MIDDLEWARE)
        )
        INTERNAL_IPS = ["127.0.0.1"]
    except ImportError:
        pass

# Email console pour le dev.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Multi-tenant : valeur par défaut explicite.
DEFAULT_TENANT = "acme"
