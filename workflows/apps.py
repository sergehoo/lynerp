from __future__ import annotations

from django.apps import AppConfig


class WorkflowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workflows"
    verbose_name = "Workflows & Notifications"

    def ready(self) -> None:
        try:
            from ai_assistant.tools import admin_tools  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
        # Branche les signaux de notifications transversaux.
        try:
            from workflows.signals import connect_signals
            connect_signals()
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("workflows.signals connect failed")
