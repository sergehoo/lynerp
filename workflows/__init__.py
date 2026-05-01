"""
Module Workflows / Notifications / Audit transversal.

- ApprovalWorkflow / ApprovalStep : circuits de validation génériques
  (n'importe quel objet peut être soumis à un workflow).
- Notification : alertes cross-canal (email, in-app).
- AuditEvent : trail centralisé pour toute action sensible.
"""

default_app_config = "workflows.apps.WorkflowsConfig"
