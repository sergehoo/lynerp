"""
Modèles du module IA transversal.

Tous les modèles métier IA héritent de ``TenantOwnedModel`` pour garantir
l'isolation multi-tenant. Aucun objet ne peut traverser les frontières
d'organisation.

Cycle de vie type d'une interaction IA :

    1. ``AIConversation`` créée pour un user/tenant.
    2. ``AIMessage`` "user" → envoi à Ollama.
    3. ``AIMessage`` "assistant" reçu, peut contenir une demande d'outil.
    4. ``AIToolCall`` enregistré (audit) ; si l'outil est read-only il
       est exécuté immédiatement, sinon une ``AIAction`` est proposée.
    5. ``AIAction`` validée par un humain → exécution déterministe.
    6. ``AIAuditLog`` trace tout (prompt, réponse, action, validation).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, TimeStampedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Configuration modèle IA (par tenant)
# --------------------------------------------------------------------------- #
class AIModelConfig(UUIDPkModel, TenantOwnedModel):
    """
    Configuration du modèle Ollama utilisé par un tenant.

    Permet à chaque organisation de choisir son propre modèle ou de surcharger
    les paramètres par défaut.
    """

    name = models.CharField(
        max_length=80,
        help_text="Identifiant interne (ex. 'default', 'recrutement-strict').",
    )
    model = models.CharField(
        max_length=120,
        default="qwen2.5:7b",
        help_text="Nom du modèle Ollama (ex. 'qwen2.5:7b', 'llama3.1:8b').",
    )
    base_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL Ollama (override l'URL globale si défini).",
    )
    temperature = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.20,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
    )
    top_p = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.90,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    max_tokens = models.PositiveIntegerField(default=2048)
    is_default = models.BooleanField(
        default=False,
        help_text="Configuration par défaut pour ce tenant.",
    )

    class Meta:
        db_table = "ai_model_config"
        verbose_name = "Configuration IA"
        verbose_name_plural = "Configurations IA"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uniq_ai_modelconfig_per_tenant",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_default=True),
                name="uniq_ai_default_modelconfig_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.model})"


# --------------------------------------------------------------------------- #
# Conversation IA
# --------------------------------------------------------------------------- #
class AIConversationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archivée"
    DELETED = "DELETED", "Supprimée"


class AIConversation(UUIDPkModel, TenantOwnedModel):
    """
    Une conversation = un fil de messages entre un utilisateur et l'IA, dans le
    contexte d'un module métier (RH, Finance, etc.) ou général.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=255, blank=True)
    module = models.CharField(
        max_length=40,
        default="general",
        help_text="Module métier de contexte (general, hr, finance, payroll, ...).",
    )
    config = models.ForeignKey(
        AIModelConfig,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    status = models.CharField(
        max_length=12,
        choices=AIConversationStatus.choices,
        default=AIConversationStatus.ACTIVE,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "ai_conversation"
        verbose_name = "Conversation IA"
        verbose_name_plural = "Conversations IA"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["tenant", "user", "-updated_at"]),
            models.Index(fields=["tenant", "module"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title or self.module} ({self.user})"

    @property
    def message_count(self) -> int:
        return self.messages.count()


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #
class AIMessageRole(models.TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "Utilisateur"
    ASSISTANT = "assistant", "Assistant"
    TOOL = "tool", "Outil"


class AIMessage(UUIDPkModel, TenantOwnedModel):
    """
    Un message dans une conversation IA. Compatible avec le format
    "messages" attendu par les API LLM (OpenAI/Ollama).
    """

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=12, choices=AIMessageRole.choices, db_index=True)
    content = models.TextField(blank=True)
    # Pour les messages "tool" : nom de l'outil + arguments + résultat.
    tool_name = models.CharField(max_length=120, blank=True)
    tool_arguments = models.JSONField(default=dict, blank=True)
    tool_result = models.JSONField(default=dict, blank=True)
    # Métadonnées : token count, latence, model utilisé, etc.
    metadata = models.JSONField(default=dict, blank=True)
    # Tokens (utile pour facturation interne / analyse usage).
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "ai_message"
        verbose_name = "Message IA"
        verbose_name_plural = "Messages IA"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["tenant", "role"]),
        ]

    def __str__(self) -> str:
        preview = (self.content or self.tool_name)[:60]
        return f"[{self.role}] {preview}"


# --------------------------------------------------------------------------- #
# Prompts système (registre versionné par module)
# --------------------------------------------------------------------------- #
class AIPromptTemplate(UUIDPkModel, TenantOwnedModel):
    """
    Prompt système versionné. Permet à un tenant d'override les prompts
    par défaut tout en gardant l'historique.

    NB : un tenant=NULL indique le prompt "global" fourni par LYNEERP.
    """

    name = models.SlugField(max_length=120, help_text="Identifiant unique : ex. 'hr.cv_analysis'.")
    module = models.CharField(max_length=40, default="general", db_index=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    template = models.TextField(help_text="Texte du prompt système avec variables Jinja2.")
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "ai_prompt_template"
        verbose_name = "Prompt IA"
        verbose_name_plural = "Prompts IA"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "version"],
                name="uniq_ai_prompt_per_tenant_version",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "module", "is_active"]),
            models.Index(fields=["name", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


# --------------------------------------------------------------------------- #
# Tool calls (audit des appels d'outils par l'IA)
# --------------------------------------------------------------------------- #
class AIToolCallStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    EXECUTED = "EXECUTED", "Exécuté"
    REJECTED = "REJECTED", "Rejeté"
    FAILED = "FAILED", "Échoué"


class AIToolCall(UUIDPkModel, TenantOwnedModel):
    """
    Enregistre chaque appel d'outil métier déclenché par l'IA.
    Permet l'audit complet de "qu'est-ce que l'IA a tenté/fait".
    """

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="tool_calls",
    )
    message = models.ForeignKey(
        AIMessage,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tool_calls",
    )
    tool_name = models.CharField(max_length=120, db_index=True)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=12,
        choices=AIToolCallStatus.choices,
        default=AIToolCallStatus.PENDING,
        db_index=True,
    )
    duration_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "ai_tool_call"
        verbose_name = "Appel d'outil IA"
        verbose_name_plural = "Appels d'outils IA"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "tool_name", "-created_at"]),
            models.Index(fields=["tenant", "status"]),
        ]


# --------------------------------------------------------------------------- #
# Actions IA (validation humaine obligatoire)
# --------------------------------------------------------------------------- #
class AIActionStatus(models.TextChoices):
    PROPOSED = "PROPOSED", "Proposée"
    APPROVED = "APPROVED", "Approuvée"
    REJECTED = "REJECTED", "Rejetée"
    EXECUTED = "EXECUTED", "Exécutée"
    FAILED = "FAILED", "Échouée"
    EXPIRED = "EXPIRED", "Expirée"


class AIAction(UUIDPkModel, TenantOwnedModel):
    """
    Action proposée par l'IA, qui doit être validée par un humain avant
    exécution réelle. Garde-fou central : aucune écriture en base ne se fait
    par l'IA seule.
    """

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_actions_proposed",
        help_text="Utilisateur qui a déclenché l'IA (initiateur).",
    )
    action_type = models.CharField(
        max_length=80,
        db_index=True,
        help_text="Identifiant logique : ex. 'hr.create_employee', 'finance.post_journal_entry'.",
    )
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, help_text="Résumé lisible (Markdown OK).")
    payload = models.JSONField(
        default=dict,
        help_text="Données structurées que l'action exécutera.",
    )
    risk_level = models.CharField(
        max_length=12,
        choices=[("LOW", "Faible"), ("MEDIUM", "Moyen"), ("HIGH", "Élevé")],
        default="MEDIUM",
    )
    status = models.CharField(
        max_length=12,
        choices=AIActionStatus.choices,
        default=AIActionStatus.PROPOSED,
        db_index=True,
    )
    requires_double_approval = models.BooleanField(
        default=False,
        help_text="Si True, deux approbateurs distincts sont nécessaires.",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_actions_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    second_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_actions_second_approved",
    )
    second_approved_at = models.DateTimeField(null=True, blank=True)

    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_actions_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    executed_at = models.DateTimeField(null=True, blank=True)
    execution_result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_action"
        verbose_name = "Action IA"
        verbose_name_plural = "Actions IA"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "action_type"]),
            models.Index(fields=["tenant", "risk_level"]),
        ]

    def __str__(self) -> str:
        return f"{self.action_type} [{self.status}]"

    @property
    def is_pending(self) -> bool:
        return self.status == AIActionStatus.PROPOSED

    @property
    def is_actionable(self) -> bool:
        if self.status != AIActionStatus.APPROVED:
            return False
        if self.requires_double_approval and not self.second_approved_by_id:
            return False
        return True


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
class AIAuditEvent(models.TextChoices):
    PROMPT_SENT = "PROMPT_SENT", "Prompt envoyé"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED", "Réponse reçue"
    TOOL_CALLED = "TOOL_CALLED", "Outil appelé"
    ACTION_PROPOSED = "ACTION_PROPOSED", "Action proposée"
    ACTION_APPROVED = "ACTION_APPROVED", "Action approuvée"
    ACTION_REJECTED = "ACTION_REJECTED", "Action rejetée"
    ACTION_EXECUTED = "ACTION_EXECUTED", "Action exécutée"
    ACTION_FAILED = "ACTION_FAILED", "Action échouée"
    PERMISSION_DENIED = "PERMISSION_DENIED", "Permission refusée"


# --------------------------------------------------------------------------- #
# Connaissance OHADA (référentiel global, NON multi-tenant)
# --------------------------------------------------------------------------- #
class OHADAActe(models.TextChoices):
    DCG = "DCG", "Acte uniforme - Droit Commercial Général"
    AUSCGIE = "AUSCGIE", "Acte uniforme - Droit des Sociétés Commerciales et du GIE"
    SURETES = "SURETES", "Acte uniforme - Sûretés"
    PROCED_COLL = "PROCED_COLL", "Acte uniforme - Procédures collectives d'apurement du passif"
    RECOUVREMENT = "RECOUVREMENT", "Acte uniforme - Procédures simplifiées de recouvrement et voies d'exécution"
    SYSCOHADA = "SYSCOHADA", "Acte uniforme - Droit Comptable et Information Financière"
    ARBITRAGE = "ARBITRAGE", "Acte uniforme - Arbitrage"
    TRANSPORT = "TRANSPORT", "Acte uniforme - Transport de Marchandises par Route"
    COOPERATIVES = "COOPERATIVES", "Acte uniforme - Sociétés Coopératives"
    MEDIATION = "MEDIATION", "Acte uniforme - Médiation"


class OHADAArticle(UUIDPkModel, TimeStampedModel):
    """
    Article ou extrait pivot d'un Acte uniforme OHADA.

    Référentiel **global** (pas multi-tenant) : le droit OHADA est commun
    aux 17 États-membres et partagé par tous les tenants. Les annotations
    privées d'un tenant passent par ``OHADANote``.

    ⚠️ Avertissement : les contenus stockés sont des **résumés-pivots** à
    valeur informative. Ne se substituent ni au texte officiel ni à la
    consultation d'un juriste OHADA agréé.
    """

    acte = models.CharField(max_length=20, choices=OHADAActe.choices, db_index=True)
    livre = models.CharField(max_length=120, blank=True)
    titre = models.CharField(max_length=180, blank=True)
    chapitre = models.CharField(max_length=180, blank=True)
    section = models.CharField(max_length=180, blank=True)

    reference = models.CharField(max_length=120, db_index=True)
    article_number = models.CharField(max_length=40, blank=True, db_index=True)

    title = models.CharField(max_length=255)
    summary = models.TextField(help_text="Résumé-pivot informatif (3-10 lignes).")
    keywords = models.JSONField(default=list, blank=True)
    related_modules = models.JSONField(
        default=list, blank=True,
        help_text="Modules ERP concernés : ['hr','payroll','finance',...]",
    )
    related_references = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    version = models.CharField(max_length=40, default="révisé")

    class Meta:
        db_table = "ohada_article"
        verbose_name = "Article OHADA"
        verbose_name_plural = "Articles OHADA"
        ordering = ["acte", "article_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["reference"],
                name="uniq_ohada_article_reference",
            ),
        ]
        indexes = [
            models.Index(fields=["acte", "is_active"]),
            models.Index(fields=["article_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.title[:60]}"

    @property
    def acte_display(self) -> str:
        return self.get_acte_display()


class OHADANote(UUIDPkModel, TenantOwnedModel):
    """Annotation tenant-privée d'un article OHADA (jurisprudence locale, mémo)."""

    article = models.ForeignKey(
        OHADAArticle, on_delete=models.CASCADE, related_name="tenant_notes",
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ohada_notes",
    )

    class Meta:
        db_table = "ohada_note"
        verbose_name = "Note OHADA tenant"
        ordering = ["-updated_at"]


class AIAuditLog(UUIDPkModel, TenantOwnedModel):
    """
    Journal d'audit immuable des activités IA. Append-only.
    """

    conversation = models.ForeignKey(
        AIConversation,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_audit_events",
    )
    event = models.CharField(max_length=24, choices=AIAuditEvent.choices, db_index=True)
    target_model = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        db_table = "ai_audit_log"
        verbose_name = "Audit IA"
        verbose_name_plural = "Audits IA"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["tenant", "event"]),
            models.Index(fields=["tenant", "actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} ({self.created_at:%Y-%m-%d %H:%M})"
