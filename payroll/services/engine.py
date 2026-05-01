"""
Moteur de calcul de paie LYNEERP.

Principe : DÉTERMINISTE, traçable, auditable. Aucun appel LLM.

Algorithme (pour un bulletin) :

    1. Charger le profil de l'employé (PayrollProfile + variables).
    2. Sélectionner les rubriques applicables (PayrollProfileItem).
    3. Calculer chaque rubrique :
       - FIXED : montant fixe (rubrique ou override profile/employé).
       - PERCENT_BASE : taux × base (gross/base_salary/social_base/taxable).
       - FROM_VARIABLE : valeur depuis ``variables`` JSON ou un Adjustment.
       - FORMULA : expression évaluée dans un sandbox restreint.
    4. Cumuler EARNINGS, DEDUCTIONS, EMPLOYER_CHARGES, INFO.
    5. Calculer base sociale, base imposable, IRPP, net.
    6. Persister Payslip + PayslipLine.

Tout est encapsulé dans une transaction atomique. Idempotent : appeler
``compute()`` plusieurs fois recrée les lignes proprement.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction
from django.utils import timezone

from payroll.models import (
    CalculationType,
    EmployeePayrollProfile,
    ItemKind,
    PayrollAdjustment,
    PayrollItem,
    PayrollPeriod,
    PayrollPeriodStatus,
    PayrollProfileItem,
    Payslip,
    PayslipLine,
    PayslipStatus,
    TaxBase,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
TWO_DEC = Decimal("0.01")


def q2(value: Decimal | float | int | str) -> Decimal:
    """Quantize à 2 décimales (banker's rounding off, ROUND_HALF_UP par défaut)."""
    return Decimal(str(value or 0)).quantize(TWO_DEC)


# --------------------------------------------------------------------------- #
# Sandbox d'évaluation de formules
# --------------------------------------------------------------------------- #
_SAFE_GLOBALS = {
    "__builtins__": {},
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "Decimal": Decimal,
}


def _eval_formula(expr: str, variables: Dict[str, Any]) -> Decimal:
    """
    Évalue une expression Python simple sur des variables nommées.
    Whitelist stricte des builtins. Les variables doivent être numériques.

    Exemples :
        "base * 0.05"
        "min(base * 0.04, 50000)"
    """
    if not expr:
        return ZERO
    safe_locals = {k: Decimal(str(v)) if not isinstance(v, Decimal) else v
                   for k, v in variables.items()}
    try:
        result = eval(expr, _SAFE_GLOBALS, safe_locals)  # noqa: S307
    except Exception as exc:  # noqa: BLE001
        logger.warning("Formule paie invalide: %s — %s", expr, exc)
        return ZERO
    return q2(result)


# --------------------------------------------------------------------------- #
# DTOs
# --------------------------------------------------------------------------- #
@dataclass
class ComputedLine:
    item_code: str
    item_id: Any
    label: str
    kind: str
    base_amount: Decimal = ZERO
    rate: Decimal = ZERO
    amount: Decimal = ZERO
    sort_order: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PayslipResult:
    employee_id: Any
    base_salary: Decimal = ZERO
    gross_amount: Decimal = ZERO
    employee_deductions: Decimal = ZERO
    employer_charges: Decimal = ZERO
    taxable_base: Decimal = ZERO
    social_base: Decimal = ZERO
    income_tax: Decimal = ZERO
    net_amount: Decimal = ZERO
    currency: str = "XOF"
    lines: List[ComputedLine] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class PayrollEngine:
    """
    Moteur de calcul d'un bulletin.

    Usage typique :

        engine = PayrollEngine(period=p)
        engine.compute_payslip(payslip)        # un bulletin
        engine.compute_period()                # tous les bulletins d'une période
    """

    def __init__(self, period: PayrollPeriod) -> None:
        if period.status == PayrollPeriodStatus.CLOSED:
            raise ValueError(f"Période {period.label} clôturée — calcul interdit.")
        self.period = period
        self.tenant = period.tenant

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def compute_period(self, *, status_filter: Iterable[str] | None = None) -> List[Payslip]:
        """Recalcule tous les bulletins de la période (filtre par statut optionnel)."""
        qs = Payslip.objects.filter(tenant=self.tenant, period=self.period)
        if status_filter:
            qs = qs.filter(status__in=list(status_filter))
        else:
            qs = qs.exclude(status__in=[PayslipStatus.PAID, PayslipStatus.CANCELLED])
        results = []
        for slip in qs.select_related("employee", "employee_profile"):
            self.compute_payslip(slip)
            results.append(slip)
        return results

    @transaction.atomic
    def compute_payslip(self, payslip: Payslip) -> Payslip:
        """Recalcule un bulletin (transactionnel, idempotent)."""
        if payslip.is_locked:
            raise ValueError("Bulletin verrouillé.")

        result = self._calculate(payslip)

        # Purge & recrée les lignes.
        payslip.lines.all().delete()
        for idx, line in enumerate(result.lines):
            PayslipLine.objects.create(
                tenant=self.tenant,
                payslip=payslip,
                item_id=line.item_id,
                label=line.label,
                kind=line.kind,
                base_amount=line.base_amount,
                rate=line.rate,
                amount=line.amount,
                sort_order=line.sort_order or (100 + idx),
                metadata=line.metadata or {},
            )

        payslip.gross_amount = result.gross_amount
        payslip.employee_deductions = result.employee_deductions
        payslip.employer_charges = result.employer_charges
        payslip.taxable_base = result.taxable_base
        payslip.social_base = result.social_base
        payslip.income_tax = result.income_tax
        payslip.net_amount = result.net_amount
        payslip.currency = result.currency
        payslip.status = PayslipStatus.COMPUTED
        payslip.computed_at = timezone.now()
        if not payslip.slip_number:
            payslip.slip_number = self._next_slip_number()
        payslip.save()
        return payslip

    # ------------------------------------------------------------------ #
    # Cœur du calcul
    # ------------------------------------------------------------------ #
    def _calculate(self, payslip: Payslip) -> PayslipResult:
        emp_profile: EmployeePayrollProfile = payslip.employee_profile
        base_salary = q2(emp_profile.base_salary)
        currency = emp_profile.currency or "XOF"
        variables: Dict[str, Decimal] = {
            "base_salary": base_salary,
        }
        # Variables custom de l'employé
        for key, val in (emp_profile.variables or {}).items():
            try:
                variables[str(key)] = Decimal(str(val))
            except Exception:  # noqa: BLE001
                continue

        # Pré-charge les ajustements indexés par item_id (pour FROM_VARIABLE
        # ou pour additionner à une rubrique).
        adjustments: Dict[Any, Decimal] = {}
        for adj in payslip.adjustments.select_related("item"):
            adjustments[adj.item_id] = adjustments.get(adj.item_id, ZERO) + q2(adj.total_amount)

        # Charge les rubriques du profil (avec overrides) triées.
        profile_items = list(
            PayrollProfileItem.objects
            .filter(profile=emp_profile.profile, tenant=self.tenant)
            .select_related("item")
            .order_by("sort_order", "item__sort_order")
        )

        # 1. Première passe : EARNINGS uniquement → on construit le brut.
        result = PayslipResult(
            employee_id=payslip.employee_id,
            base_salary=base_salary,
            currency=currency,
        )
        gross = ZERO
        social_base = ZERO
        taxable = ZERO

        for pi in profile_items:
            item: PayrollItem = pi.item
            if item.kind != ItemKind.EARNING:
                continue
            if not item.is_active:
                continue
            line = self._compute_item_line(
                item, pi, variables, adjustments,
                gross_so_far=gross, social_base=social_base, taxable=taxable,
            )
            result.lines.append(line)
            gross += line.amount
            if item.affects_social_base:
                social_base += line.amount
            if item.affects_taxable:
                taxable += line.amount
            variables["gross"] = gross
            variables["social_base"] = social_base
            variables["taxable"] = taxable

        result.gross_amount = q2(gross)
        result.social_base = q2(social_base)
        result.taxable_base = q2(taxable)

        # 2. DEDUCTIONS (cotisations salarié, IRPP)
        deductions = ZERO
        income_tax = ZERO
        for pi in profile_items:
            item = pi.item
            if item.kind != ItemKind.DEDUCTION or not item.is_active:
                continue
            line = self._compute_item_line(
                item, pi, variables, adjustments,
                gross_so_far=gross, social_base=social_base, taxable=taxable,
            )
            result.lines.append(line)
            deductions += line.amount
            if item.is_taxable:
                income_tax += line.amount
            variables["deductions"] = deductions
            variables["income_tax"] = income_tax

        result.employee_deductions = q2(deductions)
        result.income_tax = q2(income_tax)
        result.net_amount = q2(gross - deductions)

        # 3. EMPLOYER (charges patronales, hors net mais audit comptable)
        employer = ZERO
        for pi in profile_items:
            item = pi.item
            if item.kind != ItemKind.EMPLOYER or not item.is_active:
                continue
            line = self._compute_item_line(
                item, pi, variables, adjustments,
                gross_so_far=gross, social_base=social_base, taxable=taxable,
            )
            result.lines.append(line)
            employer += line.amount

        result.employer_charges = q2(employer)

        # 4. INFO (lignes informatives, ex. cumul congés, plafonds)
        for pi in profile_items:
            item = pi.item
            if item.kind != ItemKind.INFO or not item.is_active:
                continue
            line = self._compute_item_line(
                item, pi, variables, adjustments,
                gross_so_far=gross, social_base=social_base, taxable=taxable,
            )
            result.lines.append(line)

        # 5. Ajout des ajustements ponctuels orphelins (item non présent dans le profil)
        profile_item_ids = {pi.item_id for pi in profile_items}
        for adj in payslip.adjustments.select_related("item"):
            if adj.item_id in profile_item_ids:
                continue
            item = adj.item
            base = self._resolve_base(item, variables)
            amount = q2(adj.total_amount)
            line = ComputedLine(
                item_code=item.code,
                item_id=item.id,
                label=adj.label or item.name,
                kind=item.kind,
                base_amount=base,
                rate=ZERO,
                amount=amount,
                sort_order=item.sort_order or 999,
                metadata={"source": "adjustment"},
            )
            result.lines.append(line)
            if item.kind == ItemKind.EARNING:
                gross += amount
                if item.affects_social_base:
                    social_base += amount
                if item.affects_taxable:
                    taxable += amount
            elif item.kind == ItemKind.DEDUCTION:
                deductions += amount
                if item.is_taxable:
                    income_tax += amount

        # Recalculs finaux (au cas où des ajustements ont impacté les bases)
        result.gross_amount = q2(gross)
        result.employee_deductions = q2(deductions)
        result.income_tax = q2(income_tax)
        result.social_base = q2(social_base)
        result.taxable_base = q2(taxable)
        result.net_amount = q2(gross - deductions)

        return result

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _resolve_base(self, item: PayrollItem, variables: Dict[str, Decimal]) -> Decimal:
        if item.base == TaxBase.GROSS:
            return q2(variables.get("gross", ZERO))
        if item.base == TaxBase.BASE_SALARY:
            return q2(variables.get("base_salary", ZERO))
        if item.base == TaxBase.SOCIAL_BASE:
            return q2(variables.get("social_base", ZERO))
        if item.base == TaxBase.TAXABLE:
            return q2(variables.get("taxable", ZERO))
        return ZERO

    def _compute_item_line(
        self,
        item: PayrollItem,
        pi: PayrollProfileItem,
        variables: Dict[str, Decimal],
        adjustments: Dict[Any, Decimal],
        *,
        gross_so_far: Decimal,
        social_base: Decimal,
        taxable: Decimal,
    ) -> ComputedLine:
        base = self._resolve_base(item, variables)
        rate = pi.rate_override if pi.rate_override is not None else item.rate
        rate = Decimal(str(rate or 0))
        fixed = pi.amount_override if pi.amount_override is not None else item.fixed_amount
        fixed = Decimal(str(fixed or 0))

        amount = ZERO
        if item.calculation == CalculationType.FIXED:
            amount = fixed
        elif item.calculation == CalculationType.PERCENT_BASE:
            amount = q2(base * rate)
        elif item.calculation == CalculationType.FROM_VARIABLE:
            varname = item.variable_name or item.code.lower()
            amount = Decimal(str(variables.get(varname, ZERO)))
        elif item.calculation == CalculationType.FORMULA:
            amount = _eval_formula(item.formula, variables)

        # Ajout d'un éventuel ajustement sur cette rubrique.
        if item.id in adjustments:
            amount = q2(amount + adjustments[item.id])

        # Sécurité : pas de montant négatif sur une cotisation.
        if item.kind in (ItemKind.DEDUCTION, ItemKind.EMPLOYER) and amount < 0:
            amount = ZERO

        return ComputedLine(
            item_code=item.code,
            item_id=item.id,
            label=item.name,
            kind=item.kind,
            base_amount=base,
            rate=rate,
            amount=q2(amount),
            sort_order=pi.sort_order or item.sort_order or 100,
            metadata={"calculation": item.calculation},
        )

    def _next_slip_number(self) -> str:
        """Génère un numéro de bulletin chronologique : ``YYYY-MM-XXXX``."""
        prefix = f"PAY-{self.period.year}-{self.period.month:02d}"
        last = (
            Payslip.objects
            .filter(tenant=self.tenant, slip_number__startswith=prefix)
            .order_by("-slip_number")
            .values_list("slip_number", flat=True)
            .first()
        )
        if last:
            try:
                seq = int(last.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}-{seq:04d}"
