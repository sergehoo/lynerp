"""
Services internes du module IA.

- ``ollama``         : client HTTP vers Ollama (chat + streaming).
- ``prompt_registry``: prompts système versionnés par module.
- ``tool_registry``  : registre d'outils métier que l'IA peut invoquer.
- ``context``        : construction du contexte tenant/user/module.
- ``audit``          : helpers pour journaliser les événements IA.
- ``runner``         : orchestrateur d'une conversation (chain prompt → tool → réponse).
"""
from __future__ import annotations
