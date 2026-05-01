"""
Modèles du module Paie.

Schéma général :

    PayrollItem (rubrique : SALAIRE_BASE, PRIME_TRANSPORT, COTIS_CNPS, IRPP, ...)
        ▼ utilisée par
    PayrollProfile (modèle de calcul : "Cadre OHADA", "Ouvrier OHADA", ...)
        ▼ liée à
    EmployeePayrollProfile (lien employé ↔ profil + variables : salaire base)
        ▼ génère
    Payslip + PayslipLine (bulletin du mois)

Concepts clés :

- ``ItemKind`` : EARNING (gain), DEDUCTION (retenue), EMPLOYER (charges patronales),
  INFO (ligne informative non-impactante).
- ``PayrollItemRule`` : formule simple (taux × base, ou montant fixe). Évaluée
  par le ``PayrollEngine`` (déterministe, pas de LLM).
- ``PayrollAdjustment`` : ajustements ponctuels (heures sup, primes
  exceptionnelles, retenues sur salaire) appliqués à un bulletin.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from Lyneerp.core.models import TenantOwnedModel, UUIDPkModel


# --------------------------------------------------------------------------- #
# Rubriques de paie
# --------------------------------------------------------------------------- #
class ItemKind(models.TextChoices):
    EARNING = "EARNING", "Gain (brut)"
    DEDUCTION = "DEDUCTION", "Retenue salarié"
    EMPLOYER = "EMPLOYER", "Charge patronale"
    INFO = "INFO", "Information (sans impact)"


class CalculationType(models.TextChoices):
    FIXED = "FIXED", "Montant fixe"
    PERCENT_BASE = "PERCENT_BASE", "% sur une base"
    FORMULA = "FORMULA", "Formule expression simple"
    FROM_VARIABLE = "FROM_VARIABLE", "Issue d'une variable mensuelle"


class TaxBase(models.TextChoices):
    GROSS = "GROSS", "Salaire brut"
    BASE_SALARY = "BASE_SALARY", "Salaire de base"
    TAXABLE = "TAXABLE", "Salaire imposable"
    SOCIAL_BASE = "SOCIAL_BASE", "Base sociale"
    NONE = "NONE", "Aucune"


class PayrollItem(UUIDPkModel, TenantOwnedModel):
    """
    Rubrique de paie. Une rubrique est globale au tenant et peut être utilisée
    par plusieurs profils.
    """

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    kind = models.CharField(max_length=12, choices=ItemKind.choices, db_index=True)
    calculation = models.CharField(
        max_length=20,
        choices=CalculationType.choices,
        default=CalculationType.FIXED,
    )
    base = models.CharField(
        max_length=14,
        choices=TaxBase.choices,
        default=TaxBase.NONE,
    )

    # Si calculation = PERCENT_BASE → on utilise rate (ex. 0.04 pour 4 %).
    rate = models.DecimalField(
        max_digits=8, decimal_places=6,
        default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(2)],
        help_text="Taux (0-2). Ex. 0.04 = 4%.",
    )
    fixed_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        default=Decimal("0"),
        help_text="Montant fixe par défaut (override possible côté employé).",
    )
    formula = models.TextField(
        blank=True,
        help_text=(
            "Pour calculation=FORMULA. Expression Python sécurisée — ne pas "
            "y mettre du code arbitraire (le moteur whitelist les noms)."
        ),
    )
    variable_name = models.CharField(
        max_length=80, blank=True,
        help_text="Pour calculation=FROM_VARIABLE.",
    )

    # Règles d'imposition / cotisation
    affects_taxable = models.BooleanField(default=False, help_text="Inclus dans la base imposable IRPP.")
    affects_social_base = models.BooleanField(default=False, help_text="Inclus dans la base sociale (CNPS).")
    is_taxable = models.BooleanField(default=False, help_text="C'est un impôt sur salaire (IRPP).")
    is_social = models.BooleanField(default=False, help_text="C'est une cotisation sociale.")

    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "payroll_item"
        verbose_name = "Rubrique de paie"
        verbose_name_plural = "Rubriques de paie"
        ordering = ["sort_order", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uniq_payroll_item_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "kind", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


# --------------------------------------------------------------------------- #
# Profils de paie (modèles)
# --------------------------------------------------------------------------- #
class PayrollProfile(UUIDPkModel, TenantOwnedModel):
    """
    Profil de paie type : "Cadre OHADA Côte d'Ivoire", "Ouvrier OHADA Bénin"…
    Liste les rubriques par défaut applicables à un type d'employé.
    """

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    items = models.ManyToManyField(
        PayrollItem,
        through="PayrollProfileItem",
        related_name="profiles",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "payroll_profile"
        verbose_name = "Profil de paie"
        verbose_name_plural = "Profils de paie"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="uniq_payroll_profile_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PayrollProfileItem(UUIDPkModel, TenantOwnedModel):
    """Lien profil ↔ rubrique avec override possible."""

    profile = models.ForeignKey(
        PayrollProfile, on_delete=models.CASCADE, related_name="profile_items",
    )
    item = models.ForeignKey(PayrollItem, on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=100)
    rate_override = models.DecimalField(
        max_digits=8, decimal_places=6, null=True, blank=True,
        help_text="Override du taux par défaut de la rubrique.",
    )
    amount_override = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Override du montant fixe.",
    )
    is_optional = models.BooleanField(default=False)

    class Meta:
        db_table = "payroll_profile_item"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "item"],
                name="uniq_payroll_profile_item",
            ),
        ]


# --------------------------------------------------------------------------- #
# Affectation employé → profil
# --------------------------------------------------------------------------- #
class EmployeePayrollProfile(UUIDPkModel, TenantOwnedModel):
    """
    Lie un employé à un profil de paie + variables mensuelles fixes
    (salaire de base, taux personnalisés, etc.).
    """

    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="payroll_profiles",
    )
    profile = models.ForeignKey(
        PayrollProfile,
        on_delete=models.PROTECT,
        related_name="employees",
    )
    base_salary = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="XOF")
    # Pour des variables custom : ex. {"hourly_rate": 1500, "transport": 30000}
    variables = models.JSONField(default=dict, blank=True)

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "payroll_employee_profile"
        verbose_name = "Profil de paie employé"
        verbose_name_plural = "Profils de paie employés"
        indexes = [
            models.Index(fields=["tenant", "employee", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(valid_to__isnull=True)
                    | models.Q(valid_to__gte=models.F("valid_from"))
                ),
                name="payroll_emp_profile_dates_ok",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} — {self.profile.code}"


# --------------------------------------------------------------------------- #
# Périodes & bulletins
# --------------------------------------------------------------------------- #
class PayrollPeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    LOCKED = "LOCKED", "Verrouillée (calcul effectué)"
    CLOSED = "CLOSED", "Clôturée"


class PayrollPeriod(UUIDPkModel, TenantOwnedModel):
    """
    Période de paie mensuelle. La clôture (CLOSED) interdit toute modification
    des bulletins associés.
    """

    label = models.CharField(max_length=40, help_text="Ex. '2026-04', 'Avril 2026'.")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    date_start = models.DateField()
    date_end = models.DateField()
    pay_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=PayrollPeriodStatus.choices,
        default=PayrollPeriodStatus.OPEN,
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "payroll_period"
        verbose_name = "Période de paie"
        verbose_name_plural = "Périodes de paie"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "year", "month"],
                name="uniq_payroll_period_per_tenant_month",
            ),
        ]

    def __str__(self) -> str:
        return self.label


class PayslipStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    COMPUTED = "COMPUTED", "Calculé"
    APPROVED = "APPROVED", "Approuvé"
    PAID = "PAID", "Payé"
    CANCELLED = "CANCELLED", "Annulé"


class Payslip(UUIDPkModel, TenantOwnedModel):
    """Bulletin de paie d'un employé sur une période."""

    period = models.ForeignKey(
        PayrollPeriod, on_delete=models.PROTECT, related_name="payslips",
    )
    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.PROTECT, related_name="payslips",
    )
    employee_profile = models.ForeignKey(
        EmployeePayrollProfile, on_delete=models.PROTECT, related_name="payslips",
    )

    # Numéro de bulletin (auto-généré au moment du calcul)
    slip_number = models.CharField(max_length=40, blank=True, db_index=True)

    # Montants finaux (recalculés à chaque "compute()")
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    employee_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    employer_charges = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    taxable_base = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    social_base = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    income_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=10, choices=PayslipStatus.choices,
        default=PayslipStatus.DRAFT, db_index=True,
    )
    computed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payslips_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    pdf_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "payroll_payslip"
        verbose_name = "Bulletin de paie"
        verbose_name_plural = "Bulletins de paie"
        ordering = ["-period", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period", "employee"],
                name="uniq_payslip_per_employee_period",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "period", "status"]),
            models.Index(fields=["slip_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.slip_number or 'Bulletin'} — {self.employee}"

    @property
    def is_locked(self) -> bool:
        return self.status in {PayslipStatus.PAID, PayslipStatus.CANCELLED} or (
            self.period and self.period.status == PayrollPeriodStatus.CLOSED
        )


class PayslipLine(UUIDPkModel, TenantOwnedModel):
    """Une ligne de bulletin (rubrique + montant calculé)."""

    payslip = models.ForeignKey(
        Payslip, on_delete=models.CASCADE, related_name="lines",
    )
    item = models.ForeignKey(PayrollItem, on_delete=models.PROTECT)
    label = models.CharField(max_length=160)
    kind = models.CharField(max_length=12, choices=ItemKind.choices)

    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    rate = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal("0"))
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    sort_order = models.PositiveIntegerField(default=100)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payroll_payslip_line"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["payslip"]),
            models.Index(fields=["tenant", "kind"]),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.amount}"


# --------------------------------------------------------------------------- #
# Ajustements ponctuels
# --------------------------------------------------------------------------- #
class PayrollAdjustment(UUIDPkModel, TenantOwnedModel):
    """
    Ajustement ponctuel appliqué à un bulletin (heures sup, prime exceptionnelle,
    retenue, avance sur salaire, etc.). Saisi avant le calcul.
    """

    payslip = models.ForeignKey(
        Payslip, on_delete=models.CASCADE, related_name="adjustments",
    )
    item = models.ForeignKey(PayrollItem, on_delete=models.PROTECT)
    label = models.CharField(max_length=160)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1"),
    )
    unit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    note = models.TextField(blank=True)

    class Meta:
        db_table = "payroll_adjustment"
        verbose_name = "Ajustement de paie"

    @property
    def total_amount(self) -> Decimal:
        return (self.quantity or Decimal("0")) * (self.unit_amount or Decimal("0"))


# --------------------------------------------------------------------------- #
# Journal de paie (lignes par bulletin pour clôture comptable)
# --------------------------------------------------------------------------- #
class PayrollJournal(UUIDPkModel, TenantOwnedModel):
    """
    Synthèse mensuelle agrégée par tenant — utile pour intégration comptable.
    Une entrée par période + statut.
    """

    period = models.OneToOneField(
        PayrollPeriod, on_delete=models.PROTECT, related_name="journal",
    )
    total_gross = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    total_employee_deductions = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    total_employer_charges = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    total_income_tax = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    total_net = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    is_posted = models.BooleanField(default=False, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    journal_entry_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "payroll_journal"
        verbose_name = "Journal de paie"
