"""
Service d'initialisation des rubriques OHADA standards pour un tenant.

Permet à un nouveau tenant d'avoir un référentiel paie minimal opérationnel.
Les taux sont configurables et doivent être validés par un comptable avant
production. Référence : taux indicatifs OHADA / Côte d'Ivoire.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List

from django.db import transaction

from payroll.models import (
    CalculationType,
    ItemKind,
    PayrollItem,
    PayrollProfile,
    PayrollProfileItem,
    TaxBase,
)

logger = logging.getLogger(__name__)


# Catalogue de rubriques OHADA simplifiées. À adapter par pays.
OHADA_DEFAULT_ITEMS: List[Dict[str, Any]] = [
    # ---------------------- Gains ----------------------
    {
        "code": "SAL_BASE", "name": "Salaire de base",
        "kind": ItemKind.EARNING, "calculation": CalculationType.FROM_VARIABLE,
        "variable_name": "base_salary",
        "affects_taxable": True, "affects_social_base": True,
        "sort_order": 10,
    },
    {
        "code": "PRIME_TRANSPORT", "name": "Prime de transport",
        "kind": ItemKind.EARNING, "calculation": CalculationType.FIXED,
        "fixed_amount": "30000",
        "affects_taxable": False, "affects_social_base": False,
        "sort_order": 20,
    },
    {
        "code": "PRIME_PERF", "name": "Prime de performance",
        "kind": ItemKind.EARNING, "calculation": CalculationType.FIXED,
        "fixed_amount": "0",
        "affects_taxable": True, "affects_social_base": True,
        "sort_order": 30,
    },
    {
        "code": "HEURES_SUP", "name": "Heures supplémentaires",
        "kind": ItemKind.EARNING, "calculation": CalculationType.FROM_VARIABLE,
        "variable_name": "overtime",
        "affects_taxable": True, "affects_social_base": True,
        "sort_order": 40,
    },
    # ---------------------- Retenues salarié ----------------------
    {
        "code": "CNPS_SAL", "name": "CNPS — part salariale",
        "kind": ItemKind.DEDUCTION, "calculation": CalculationType.PERCENT_BASE,
        "base": TaxBase.SOCIAL_BASE, "rate": "0.063",  # 6.3 % indicatif
        "is_social": True,
        "sort_order": 110,
    },
    {
        "code": "ITS", "name": "Impôt sur Traitements & Salaires (ITS/IRPP)",
        "kind": ItemKind.DEDUCTION, "calculation": CalculationType.PERCENT_BASE,
        "base": TaxBase.TAXABLE, "rate": "0.10",  # taux moyen indicatif
        "is_taxable": True,
        "sort_order": 120,
    },
    {
        "code": "AVANCE_SAL", "name": "Avance sur salaire",
        "kind": ItemKind.DEDUCTION, "calculation": CalculationType.FROM_VARIABLE,
        "variable_name": "salary_advance",
        "sort_order": 130,
    },
    # ---------------------- Charges patronales ----------------------
    {
        "code": "CNPS_PAT", "name": "CNPS — part patronale",
        "kind": ItemKind.EMPLOYER, "calculation": CalculationType.PERCENT_BASE,
        "base": TaxBase.SOCIAL_BASE, "rate": "0.165",  # 16.5 % indicatif
        "is_social": True,
        "sort_order": 210,
    },
    {
        "code": "ACCIDENT_TRAV", "name": "Accidents du travail",
        "kind": ItemKind.EMPLOYER, "calculation": CalculationType.PERCENT_BASE,
        "base": TaxBase.SOCIAL_BASE, "rate": "0.02",
        "is_social": True,
        "sort_order": 220,
    },
    # ---------------------- Info ----------------------
    {
        "code": "INFO_NET_AVANT_TAX", "name": "Net avant impôt",
        "kind": ItemKind.INFO, "calculation": CalculationType.FORMULA,
        "formula": "gross - deductions + income_tax",
        "sort_order": 900,
    },
]


# Profils standards (sets de rubriques à appliquer)
OHADA_DEFAULT_PROFILES = [
    {
        "code": "OHADA_EMPLOYE",
        "name": "Profil OHADA — Employé standard",
        "description": "Profil de paie standard OHADA pour employés non-cadres.",
        "items": [
            "SAL_BASE", "PRIME_TRANSPORT", "PRIME_PERF", "HEURES_SUP",
            "CNPS_SAL", "ITS", "AVANCE_SAL",
            "CNPS_PAT", "ACCIDENT_TRAV",
            "INFO_NET_AVANT_TAX",
        ],
    },
    {
        "code": "OHADA_CADRE",
        "name": "Profil OHADA — Cadre",
        "description": "Profil de paie OHADA pour personnel cadre.",
        "items": [
            "SAL_BASE", "PRIME_TRANSPORT", "PRIME_PERF",
            "CNPS_SAL", "ITS",
            "CNPS_PAT", "ACCIDENT_TRAV",
            "INFO_NET_AVANT_TAX",
        ],
    },
]


@transaction.atomic
def seed_ohada_payroll(tenant) -> Dict[str, Any]:
    """
    Crée les rubriques + profils OHADA standards si absents.
    Idempotent : ne touche pas aux rubriques existantes.
    """
    created_items = []
    items_by_code: Dict[str, PayrollItem] = {}

    for spec in OHADA_DEFAULT_ITEMS:
        spec = dict(spec)
        # Decimal converters
        if "fixed_amount" in spec:
            spec["fixed_amount"] = Decimal(spec["fixed_amount"])
        if "rate" in spec:
            spec["rate"] = Decimal(spec["rate"])
        item, created = PayrollItem.objects.get_or_create(
            tenant=tenant, code=spec["code"],
            defaults=spec,
        )
        items_by_code[item.code] = item
        if created:
            created_items.append(item.code)

    created_profiles = []
    for prof_spec in OHADA_DEFAULT_PROFILES:
        prof, created = PayrollProfile.objects.get_or_create(
            tenant=tenant, code=prof_spec["code"],
            defaults={
                "name": prof_spec["name"],
                "description": prof_spec["description"],
            },
        )
        # Liaison items
        for idx, code in enumerate(prof_spec["items"]):
            item = items_by_code.get(code)
            if not item:
                continue
            PayrollProfileItem.objects.get_or_create(
                tenant=tenant, profile=prof, item=item,
                defaults={"sort_order": (idx + 1) * 10},
            )
        if created:
            created_profiles.append(prof.code)

    return {
        "created_items": created_items,
        "created_profiles": created_profiles,
        "total_items": len(items_by_code),
    }
