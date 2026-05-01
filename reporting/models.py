"""
Modèles Reporting / BI.

Dashboard contient des Widgets. Chaque widget pointe sur un KPI logique
(``kpi_code``). Le calcul est délégué à un registre côté ``services``.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


class WidgetType(models.TextChoices):
    KPI = "KPI", "KPI numérique"
    LINE = "LINE", "Courbe"
    BAR = "BAR", "Barres"
    PIE = "PIE", "Camembert"
    TABLE = "TABLE", "Tableau"


class Dashboard(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False, help_text="Visible par tous les membres du tenant.")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="dashboards",
    )

    class Meta:
        db_table = "reporting_dashboard"
        verbose_name = "Tableau de bord"
        ordering = ["name"]


class Widget(UUIDPkModel, TenantOwnedModel):
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE, related_name="widgets",
    )
    title = models.CharField(max_length=160)
    type = models.CharField(max_length=8, choices=WidgetType.choices)
    kpi_code = models.CharField(
        max_length=80,
        help_text="Identifiant du calcul (ex. 'hr.headcount', 'finance.cash_balance').",
    )
    config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "reporting_widget"
        ordering = ["dashboard", "sort_order"]


class KPISnapshot(UUIDPkModel, TenantOwnedModel):
    """Stockage périodique d'une valeur KPI (pour graphiques temporels)."""

    kpi_code = models.CharField(max_length=80, db_index=True)
    captured_at = models.DateTimeField()
    value = models.DecimalField(max_digits=18, decimal_places=4)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "reporting_kpi_snapshot"
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["tenant", "kpi_code", "-captured_at"]),
        ]
