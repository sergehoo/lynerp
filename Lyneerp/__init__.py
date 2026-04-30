"""
LYNEERP — package racine du projet Django.

On expose ``celery_app`` ici pour que Celery soit prêt dès qu'un worker
ou Django importe le projet : c'est la convention recommandée par la doc Celery
(https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).
"""
from __future__ import annotations

# L'import est volontairement protégé : il ne casse pas si Celery n'est pas
# installé (ex. environnements minimaux de tests).
try:
    from .celery import app as celery_app  # noqa: F401

    __all__ = ("celery_app",)
except Exception:  # pragma: no cover
    celery_app = None
    __all__ = ()
