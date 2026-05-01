"""
Registre des prompts système par module.

Stratégie :
1. Les prompts par défaut sont définis dans ``ai_assistant/prompts/*.py``.
2. Un tenant peut créer un ``AIPromptTemplate`` actif portant le même ``name``
   pour overrider le prompt par défaut.
3. Le rendu interpole les variables fournies via ``str.format_map`` (sans
   dépendance externe).
"""
from __future__ import annotations

import logging
from string import Formatter
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class _SafeDict(dict):
    """Renvoie ``{var}`` au lieu de lever KeyError pour une variable absente."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class PromptRegistry:
    """
    Registre central des prompts. Charge à la demande depuis :

      1. La DB (AIPromptTemplate) — override par tenant.
      2. Les modules ``ai_assistant.prompts`` — fallback global.
    """

    _DEFAULTS: Dict[str, str] = {}

    @classmethod
    def register_default(cls, name: str, template: str) -> None:
        cls._DEFAULTS[name] = template

    def render(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        tenant=None,
    ) -> str:
        template = self._lookup(name, tenant=tenant)
        if template is None:
            logger.warning("Prompt template '%s' introuvable", name)
            return ""

        ctx = _SafeDict(**(context or {}))
        try:
            return Formatter().vformat(template, (), ctx)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to render prompt %s", name)
            return template

    # ----------------------------------------------------------------------- #
    # Lookup hiérarchique
    # ----------------------------------------------------------------------- #
    def _lookup(self, name: str, tenant=None) -> Optional[str]:
        # 1) Override DB tenant
        if tenant is not None:
            try:
                from ai_assistant.models import AIPromptTemplate

                tpl = (
                    AIPromptTemplate.objects
                    .filter(tenant=tenant, name=name, is_active=True)
                    .order_by("-version")
                    .first()
                )
                if tpl is not None:
                    return tpl.template
            except Exception:  # noqa: BLE001
                logger.exception("DB prompt lookup failed for %s", name)

        # 2) Default in-code
        if name in self._DEFAULTS:
            return self._DEFAULTS[name]

        # 3) Lazy import des prompts par module
        try:
            module_key = name.split(".", 1)[0] if "." in name else "general"
            module = __import__(f"ai_assistant.prompts.{module_key}", fromlist=["PROMPTS"])
            prompts: Dict[str, str] = getattr(module, "PROMPTS", {}) or {}
            if name in prompts:
                self._DEFAULTS[name] = prompts[name]
                return prompts[name]
        except ImportError:
            return None

        return None


_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
