from __future__ import annotations

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
    verbose_name = "Logistique / Stock"

    def ready(self) -> None:
        # Branchement signal post_save → maj Inventory + alertes
        from inventory import signals  # noqa: F401
        try:
            from ai_assistant.tools import inventory_tools  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
