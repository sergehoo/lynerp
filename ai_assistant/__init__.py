"""
Module IA transversal de LYNEERP.

Fournit un assistant métier intelligent intégré aux modules ERP :
- chatbot global et contextuel par module
- analyse de données, scoring, recommandations
- génération de documents et de rapports
- détection d'anomalies
- aide à la décision

Garde-fous :
- isolation stricte multi-tenant
- aucune action irréversible sans validation humaine (AIAction)
- audit trail complet (AIAuditLog)
- masquage des données sensibles dans les prompts
"""

default_app_config = "ai_assistant.apps.AIAssistantConfig"
