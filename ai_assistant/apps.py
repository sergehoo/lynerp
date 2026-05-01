from __future__ import annotations

from django.apps import AppConfig


class AIAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_assistant"
    verbose_name = "Assistant IA"

    def ready(self) -> None:
        # Charge le registre d'outils (auto-discovery côté apps).
        from ai_assistant.services import tool_registry  # noqa: F401
