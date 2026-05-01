from __future__ import annotations

from django.apps import AppConfig


class CRMConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"
    verbose_name = "CRM"

    def ready(self) -> None:
        try:
            from ai_assistant.tools import crm_tools  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
