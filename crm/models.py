"""
Modèles du module CRM.

    Account (entreprise / client) ──► Contact (personnes)
                                  ──► Opportunity (deal)
                                       └─► Pipeline + Stage
                                       └─► Activity (rdv, appels, mails)
    Lead (prospect non qualifié) — converti en Account + Contact + Opportunity
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Comptes & contacts
# --------------------------------------------------------------------------- #
class AccountType(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Client"
    PROSPECT = "PROSPECT", "Prospect"
    PARTNER = "PARTNER", "Partenaire"
    COMPETITOR = "COMPETITOR", "Concurrent"


class Industry(models.TextChoices):
    FINANCE = "FINANCE", "Finance"
    AGRO = "AGRO", "Agro-alimentaire"
    TELECOM = "TELECOM", "Télécom"
    PUBLIC = "PUBLIC", "Secteur public"
    INDUSTRY = "INDUSTRY", "Industrie"
    SERVICES = "SERVICES", "Services"
    RETAIL = "RETAIL", "Distribution"
    HEALTH = "HEALTH", "Santé"
    EDUCATION = "EDUCATION", "Éducation"
    OTHER = "OTHER", "Autre"


class Account(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    type = models.CharField(
        max_length=12, choices=AccountType.choices,
        default=AccountType.PROSPECT, db_index=True,
    )
    industry = models.CharField(
        max_length=12, choices=Industry.choices,
        default=Industry.OTHER, blank=True,
    )
    website = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    billing_address = models.TextField(blank=True)
    annual_revenue = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    employees_count = models.PositiveIntegerField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="crm_accounts",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_account"
        verbose_name = "Compte client/prospect"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "type", "is_active"]),
            models.Index(fields=["tenant", "owner"]),
        ]

    def __str__(self) -> str:
        return self.name


class Contact(UUIDPkModel, TenantOwnedModel):
    account = models.ForeignKey(
        Account, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="contacts",
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    mobile = models.CharField(max_length=40, blank=True)
    department = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    do_not_contact = models.BooleanField(default=False)

    class Meta:
        db_table = "crm_contact"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["tenant", "account"]),
            models.Index(fields=["tenant", "email"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


# --------------------------------------------------------------------------- #
# Pipelines & stages
# --------------------------------------------------------------------------- #
class Pipeline(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_pipeline"
        verbose_name = "Pipeline"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"], name="uniq_crm_pipeline_per_tenant",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_default=True),
                name="uniq_crm_default_pipeline_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Stage(UUIDPkModel, TenantOwnedModel):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    order = models.PositiveSmallIntegerField()
    probability = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Probabilité de gain (%) pour les opportunités à ce stade.",
    )
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)

    class Meta:
        db_table = "crm_stage"
        ordering = ["pipeline", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline", "order"], name="uniq_crm_stage_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pipeline.code} / {self.name}"


# --------------------------------------------------------------------------- #
# Opportunités
# --------------------------------------------------------------------------- #
class OpportunityStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    WON = "WON", "Gagnée"
    LOST = "LOST", "Perdue"
    ABANDONED = "ABANDONED", "Abandonnée"


class Opportunity(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=200)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="opportunities")
    primary_contact = models.ForeignKey(
        Contact, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="opportunities",
    )
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name="opportunities")
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="opportunities")
    status = models.CharField(
        max_length=12, choices=OpportunityStatus.choices,
        default=OpportunityStatus.OPEN, db_index=True,
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="XOF")
    expected_close_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    win_probability = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="crm_opportunities",
    )
    description = models.TextField(blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    # Score IA (mis à jour par l'outil crm.score_lead).
    ai_score = models.PositiveSmallIntegerField(null=True, blank=True)
    ai_score_explanation = models.TextField(blank=True)

    class Meta:
        db_table = "crm_opportunity"
        verbose_name = "Opportunité"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "stage"]),
            models.Index(fields=["tenant", "owner"]),
            models.Index(fields=["tenant", "expected_close_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.amount} {self.currency}"

    @property
    def weighted_amount(self) -> Decimal:
        return (self.amount or Decimal("0")) * (self.win_probability or Decimal("0")) / Decimal("100")


# --------------------------------------------------------------------------- #
# Leads (prospects non qualifiés)
# --------------------------------------------------------------------------- #
class LeadStatus(models.TextChoices):
    NEW = "NEW", "Nouveau"
    CONTACTED = "CONTACTED", "Contacté"
    QUALIFIED = "QUALIFIED", "Qualifié"
    UNQUALIFIED = "UNQUALIFIED", "Non qualifié"
    CONVERTED = "CONVERTED", "Converti"


class Lead(UUIDPkModel, TenantOwnedModel):
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=80, blank=True, help_text="Web, salon, parrainage, etc.")
    status = models.CharField(
        max_length=14, choices=LeadStatus.choices,
        default=LeadStatus.NEW, db_index=True,
    )
    industry = models.CharField(
        max_length=12, choices=Industry.choices,
        default=Industry.OTHER, blank=True,
    )
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="crm_leads",
    )
    converted_account = models.ForeignKey(
        Account, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="converted_from_leads",
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    ai_score = models.PositiveSmallIntegerField(null=True, blank=True)
    ai_score_explanation = models.TextField(blank=True)

    class Meta:
        db_table = "crm_lead"
        verbose_name = "Lead"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "owner"]),
        ]


# --------------------------------------------------------------------------- #
# Activités (rdv, appels, mails…)
# --------------------------------------------------------------------------- #
class ActivityType(models.TextChoices):
    CALL = "CALL", "Appel"
    EMAIL = "EMAIL", "Email"
    MEETING = "MEETING", "Rendez-vous"
    TASK = "TASK", "Tâche"
    NOTE = "NOTE", "Note"


class ActivityStatus(models.TextChoices):
    PLANNED = "PLANNED", "Planifiée"
    DONE = "DONE", "Effectuée"
    CANCELLED = "CANCELLED", "Annulée"


class Activity(UUIDPkModel, TenantOwnedModel):
    type = models.CharField(max_length=10, choices=ActivityType.choices)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ActivityStatus.choices,
        default=ActivityStatus.PLANNED, db_index=True,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)

    # Liens
    account = models.ForeignKey(
        Account, null=True, blank=True,
        on_delete=models.CASCADE, related_name="activities",
    )
    contact = models.ForeignKey(
        Contact, null=True, blank=True,
        on_delete=models.CASCADE, related_name="activities",
    )
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True,
        on_delete=models.CASCADE, related_name="activities",
    )
    lead = models.ForeignKey(
        Lead, null=True, blank=True,
        on_delete=models.CASCADE, related_name="activities",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="crm_activities",
    )

    class Meta:
        db_table = "crm_activity"
        verbose_name = "Activité CRM"
        ordering = ["-scheduled_at", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "type", "status"]),
            models.Index(fields=["tenant", "assigned_to"]),
        ]

    def __str__(self) -> str:
        return f"[{self.type}] {self.subject}"
