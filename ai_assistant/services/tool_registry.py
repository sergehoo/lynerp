"""
Registre d'outils que l'IA peut invoquer.

Chaque outil a :

- un identifiant unique (ex. ``hr.analyze_resume``) ;
- une description ;
- un schéma JSON d'arguments ;
- un niveau de risque (``read`` / ``write`` / ``destructive``) ;
- une fonction Python qui exécute l'outil ;
- une vérification de permission (DRF-like).

Si un outil est ``write`` ou ``destructive``, son exécution **NE SE FAIT PAS**
directement : on crée une ``AIAction`` en statut PROPOSED et on attend la
validation humaine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Niveaux de risque : déterminent si l'outil s'exécute auto ou via AIAction.
RISK_READ = "read"
RISK_WRITE = "write"
RISK_DESTRUCTIVE = "destructive"


@dataclass
class AITool:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = RISK_READ
    schema: Dict[str, Any] = field(default_factory=dict)
    required_roles: List[str] = field(default_factory=list)
    module: str = "general"

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Format compatible function-calling style OpenAI/Ollama 0.4+.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema or {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        }

    def is_writeable(self) -> bool:
        return self.risk in (RISK_WRITE, RISK_DESTRUCTIVE)


class AIToolRegistry:
    """Registre singleton des outils."""

    def __init__(self) -> None:
        self._tools: Dict[str, AITool] = {}

    # ----------------------------------------------------------------------- #
    # Enregistrement
    # ----------------------------------------------------------------------- #
    def register(self, tool: AITool) -> None:
        if tool.name in self._tools:
            logger.warning("Outil IA '%s' déjà enregistré, override.", tool.name)
        self._tools[tool.name] = tool

    def tool(
        self,
        name: str,
        description: str,
        *,
        risk: str = RISK_READ,
        schema: Optional[Dict[str, Any]] = None,
        required_roles: Optional[List[str]] = None,
        module: str = "general",
    ):
        """
        Decorator pour enregistrer un handler comme outil.

            @registry.tool("hr.analyze_resume", "Analyse un CV", risk=RISK_READ)
            def analyze(*, application_id: str, tenant, user) -> dict: ...
        """
        def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.register(AITool(
                name=name, description=description, handler=fn,
                risk=risk, schema=schema or {},
                required_roles=required_roles or [], module=module,
            ))
            return fn

        return _wrap

    # ----------------------------------------------------------------------- #
    # Lecture
    # ----------------------------------------------------------------------- #
    def get(self, name: str) -> Optional[AITool]:
        return self._tools.get(name)

    def list(self, module: Optional[str] = None) -> List[AITool]:
        items = list(self._tools.values())
        if module:
            items = [t for t in items if t.module == module]
        return items

    def list_for_module(self, module: str) -> List[AITool]:
        # Toujours expose les outils "general" en plus de ceux du module.
        return [t for t in self._tools.values() if t.module in {module, "general"}]


_registry: Optional[AIToolRegistry] = None


def get_tool_registry() -> AIToolRegistry:
    global _registry
    if _registry is None:
        _registry = AIToolRegistry()
        # Auto-import des modules d'outils pour qu'ils s'enregistrent.
        # Chaque import est protégé : si une app n'est pas installée, on
        # continue sans bloquer le projet.
        for mod in (
            "ai_assistant.tools.general_tools",
            "ai_assistant.tools.hr_tools",
            "ai_assistant.tools.finance_tools",
            "ai_assistant.tools.payroll_tools",
            "ai_assistant.tools.inventory_tools",
            "ai_assistant.tools.admin_tools",
            "ai_assistant.tools.ohada_tools",
            "ai_assistant.tools.crm_tools",
            "ai_assistant.tools.projects_tools",
        ):
            try:
                __import__(mod)
            except ImportError:
                logger.debug("Tools module %s indisponible", mod)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to load %s", mod)
    return _registry
