from __future__ import annotations

from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projects"
    verbose_name = "Projets"

    def ready(self) -> None:
        try:
            from ai_assistant.tools import projects_tools  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
