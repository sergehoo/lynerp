"""
Modèles du module Projets.

    Project ──► Phase ──► Task
              ├─► Milestone
              └─► ProjectMember (lien employé / user + rôle)

    TimeEntry : pointage temps lié à une Task
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Projets
# --------------------------------------------------------------------------- #
class ProjectStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    ACTIVE = "ACTIVE", "Actif"
    ON_HOLD = "ON_HOLD", "En pause"
    COMPLETED = "COMPLETED", "Terminé"
    CANCELLED = "CANCELLED", "Annulé"


class Project(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ProjectStatus.choices,
        default=ProjectStatus.DRAFT, db_index=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Lien optionnel CRM / Client
    customer_account = models.ForeignKey(
        "crm.Account", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="projects",
    )
    related_opportunity = models.ForeignKey(
        "crm.Opportunity", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="projects",
    )

    budget = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    currency = models.CharField(max_length=3, default="XOF")
    progress_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="projects_managed",
    )

    class Meta:
        db_table = "projects_project"
        verbose_name = "Projet"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"], name="uniq_project_code_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "project_manager"]),
        ]

    def __str__(self) -> str:
        return f"[{self.code}] {self.name}"


class Phase(UUIDPkModel, TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    progress_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
    )

    class Meta:
        db_table = "projects_phase"
        ordering = ["project", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "order"], name="uniq_project_phase_order",
            ),
        ]


# --------------------------------------------------------------------------- #
# Tâches & jalons
# --------------------------------------------------------------------------- #
class TaskPriority(models.TextChoices):
    LOW = "LOW", "Bas"
    NORMAL = "NORMAL", "Normal"
    HIGH = "HIGH", "Élevé"
    URGENT = "URGENT", "Urgent"


class TaskStatus(models.TextChoices):
    TODO = "TODO", "À faire"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    REVIEW = "REVIEW", "À valider"
    DONE = "DONE", "Terminé"
    BLOCKED = "BLOCKED", "Bloqué"
    CANCELLED = "CANCELLED", "Annulé"


class Task(UUIDPkModel, TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    phase = models.ForeignKey(
        Phase, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tasks",
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.CASCADE, related_name="subtasks",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=14, choices=TaskStatus.choices,
        default=TaskStatus.TODO, db_index=True,
    )
    priority = models.CharField(
        max_length=8, choices=TaskPriority.choices,
        default=TaskPriority.NORMAL,
    )

    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="project_tasks",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="project_tasks_reported",
    )

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    estimated_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    spent_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    progress_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
    )

    tags = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "projects_task"
        verbose_name = "Tâche"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "project", "status"]),
            models.Index(fields=["tenant", "due_date"]),
        ]


class Milestone(UUIDPkModel, TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    achieved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "projects_milestone"
        verbose_name = "Jalon"
        ordering = ["target_date"]


# --------------------------------------------------------------------------- #
# Membres & temps
# --------------------------------------------------------------------------- #
class ProjectRole(models.TextChoices):
    MANAGER = "MANAGER", "Chef de projet"
    LEAD = "LEAD", "Lead"
    CONTRIBUTOR = "CONTRIBUTOR", "Contributeur"
    OBSERVER = "OBSERVER", "Observateur"


class ProjectMember(UUIDPkModel, TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships",
    )
    role = models.CharField(
        max_length=12, choices=ProjectRole.choices,
        default=ProjectRole.CONTRIBUTOR,
    )
    daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
        help_text="Coût journalier interne (TJM).",
    )
    allocation_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("100"),
        help_text="Pourcentage d'allocation sur le projet.",
    )

    class Meta:
        db_table = "projects_member"
        verbose_name = "Membre projet"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"], name="uniq_project_member",
            ),
        ]


class TimeEntry(UUIDPkModel, TenantOwnedModel):
    """Pointage temps : un user passe X heures sur une tâche à une date."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_entries",
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="time_entries")
    task = models.ForeignKey(
        Task, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="time_entries",
    )
    work_date = models.DateField()
    hours = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)],
    )
    description = models.TextField(blank=True)
    is_billable = models.BooleanField(default=True)

    class Meta:
        db_table = "projects_time_entry"
        verbose_name = "Pointage de temps"
        ordering = ["-work_date"]
        indexes = [
            models.Index(fields=["tenant", "user", "-work_date"]),
            models.Index(fields=["tenant", "project", "-work_date"]),
        ]
