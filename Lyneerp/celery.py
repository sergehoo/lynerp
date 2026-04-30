"""
Configuration Celery pour LYNEERP.

- Le broker et le backend sont lus depuis l'environnement.
- Toutes les tâches définies dans les apps sont auto-découvertes
  (`hr.tasks`, `finance.tasks`, etc.).
- Le scheduler Celery Beat utilise la base Django (`django-celery-beat`)
  s'il est installé, sinon un schedule fichier en mémoire.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

# Choix du module settings selon DJANGO_ENV (dev par défaut).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Lyneerp.settings")

app = Celery("lyneerp")

# Charge la config Celery depuis les settings Django (clés `CELERY_*`).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discovery des modules `tasks.py` dans toutes les apps installées.
app.autodiscover_tasks()


@app.task(bind=True, name="Lyneerp.celery.ping")
def ping(self) -> str:
    """Tâche de santé Celery (utile pour healthcheck)."""
    return "pong"


# --- Scheduler par défaut --------------------------------------------------- #
# Si vous voulez piloter par variables d'env, déplacez ce dict dans settings.
app.conf.beat_schedule = {
    "ping-every-15min": {
        "task": "Lyneerp.celery.ping",
        "schedule": crontab(minute="*/15"),
    },
}
