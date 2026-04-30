"""
Settings dédiés aux tests automatisés (pytest / Django TestCase).

Optimisations :
- backend de hash mot de passe rapide
- email collecté en mémoire
- cache LocMem
- DB SQLite en mémoire si DB_ENGINE non explicite
"""
from __future__ import annotations

import os

# Forcer SQLite en mémoire si la conf prod/dev n'a pas été surchargée.
os.environ.setdefault("DB_ENGINE", "sqlite")
os.environ.setdefault("DB_NAME", ":memory:")

from .base import *  # noqa: E402,F401,F403

DEBUG = False
TESTING = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "lyneerp-tests",
    }
}

# Désactiver Celery réel en tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
