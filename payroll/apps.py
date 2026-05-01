from __future__ import annotations

from django.apps import AppConfig


class PayrollConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payroll"
    verbose_name = "Paie"

    def ready(self) -> None:
        # Auto-import des outils IA paie (s'enregistrent au registre).
        try:
            from ai_assistant.tools import payroll_tools  # noqa: F401
        except Exception:  # noqa: BLE001
            # Module ai_assistant peut ne pas être chargé en isolement (tests).
            pass
