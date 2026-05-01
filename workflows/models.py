"""
Modèles transversaux : workflows d'approbation, notifications, audit.

ApprovalWorkflow + ApprovalStep définissent un circuit générique. Une
``ApprovalRequest`` lie n'importe quel objet métier (via GenericForeignKey)
à un workflow et trace les approbations successives.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Workflows d'approbation
# --------------------------------------------------------------------------- #
class ApprovalWorkflow(UUIDPkModel, TenantOwnedModel):
    """
    Un workflow définit une série d'étapes (ApprovalStep) avec ordre.
    Exemples : "Approbation BC > 1M XOF", "Validation paie", "Validation contrat".
    """

    code = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_model = models.CharField(
        max_length=120,
        help_text="Identifiant du modèle ciblé (ex. 'inventory.PurchaseOrder').",
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "wf_workflow"
        verbose_name = "Workflow d'approbation"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uniq_wf_code_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ApprovalStep(UUIDPkModel, TenantOwnedModel):
    workflow = models.ForeignKey(
        ApprovalWorkflow, on_delete=models.CASCADE, related_name="steps",
    )
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField()
    role_required = models.CharField(
        max_length=40, blank=True,
        help_text="Rôle TenantUser requis (OWNER, ADMIN, MANAGER, ...). Vide = quiconque.",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approval_steps",
        help_text="Approbateur fixe (override role).",
    )
    is_optional = models.BooleanField(default=False)

    class Meta:
        db_table = "wf_step"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "order"],
                name="uniq_wf_step_order",
            ),
        ]


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    APPROVED = "APPROVED", "Approuvée"
    REJECTED = "REJECTED", "Rejetée"
    CANCELLED = "CANCELLED", "Annulée"


class ApprovalRequest(UUIDPkModel, TenantOwnedModel):
    """
    Une demande d'approbation rattache un objet métier (n'importe lequel)
    à un workflow et suit le statut global.
    """

    workflow = models.ForeignKey(
        ApprovalWorkflow, on_delete=models.PROTECT, related_name="requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    # GenericForeignKey vers l'objet ciblé
    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL,
    )
    object_id = models.CharField(max_length=64, blank=True)
    target = GenericForeignKey("content_type", "object_id")

    current_step = models.ForeignKey(
        ApprovalStep, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="active_requests",
    )
    status = models.CharField(
        max_length=12, choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING, db_index=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "wf_request"
        verbose_name = "Demande d'approbation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "workflow"]),
        ]


class ApprovalDecision(UUIDPkModel, TenantOwnedModel):
    """Trace de chaque décision d'un approbateur sur une étape."""

    request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name="decisions",
    )
    step = models.ForeignKey(ApprovalStep, on_delete=models.PROTECT)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    decision = models.CharField(
        max_length=10,
        choices=[("APPROVE", "Approuvé"), ("REJECT", "Rejeté")],
    )
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wf_decision"
        ordering = ["-decided_at"]


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
class NotificationLevel(models.TextChoices):
    INFO = "INFO", "Information"
    SUCCESS = "SUCCESS", "Succès"
    WARNING = "WARNING", "Avertissement"
    ERROR = "ERROR", "Erreur"


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", "Application"
    EMAIL = "EMAIL", "Email"
    WEBHOOK = "WEBHOOK", "Webhook"


class Notification(UUIDPkModel, TenantOwnedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    level = models.CharField(
        max_length=10, choices=NotificationLevel.choices,
        default=NotificationLevel.INFO,
    )
    channel = models.CharField(
        max_length=10, choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
    )
    url = models.CharField(max_length=255, blank=True, help_text="Lien d'action.")
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # GenericForeignKey optionnel vers l'objet métier source
    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL,
    )
    object_id = models.CharField(max_length=64, blank=True)
    target = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "wf_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user", "-created_at"]),
            models.Index(fields=["tenant", "read_at"]),
        ]


# --------------------------------------------------------------------------- #
# Audit transversal
# --------------------------------------------------------------------------- #
class AuditEvent(UUIDPkModel, TenantOwnedModel):
    """
    Journal d'audit cross-module. Différent de ``ai_assistant.AIAuditLog``
    qui est dédié aux actions IA.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_events",
    )
    event_type = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(
        max_length=10,
        choices=[
            ("LOW", "Bas"),
            ("MEDIUM", "Moyen"),
            ("HIGH", "Élevé"),
            ("CRITICAL", "Critique"),
        ],
        default="LOW",
    )
    target_model = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        db_table = "wf_audit_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "event_type", "-created_at"]),
            models.Index(fields=["tenant", "severity"]),
        ]
