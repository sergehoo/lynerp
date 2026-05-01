"""
Module Paie LYNEERP.

Architecture :
- Modèles : rubriques, profils, bulletins, ajustements (multi-tenant)
- Moteur déterministe : calcul brut → cotisations → net (services/engine.py)
- IA : explication bulletin, détection anomalies, simulation (outils ai_assistant)

Garde-fou : aucun calcul réglementaire n'est délégué au LLM. Le moteur est
testable, traçable, auditable.
"""

default_app_config = "payroll.apps.PayrollConfig"
