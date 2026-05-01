"""
Registre des executors d'AIAction.

Un executor est une fonction qui prend ``ai_action`` + ``user`` et exécute
réellement la modification en base. Il est appelé UNIQUEMENT quand l'action
est approuvée (passé par le workflow).

Convention d'enregistrement :

    @register_executor("finance.post_journal_entry")
    def post_journal_entry(*, ai_action, user) -> dict:
        ...
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_EXECUTORS: Dict[str, Callable[..., Dict[str, Any]]] = {}


def register_executor(action_type: str):
    def _wrap(fn: Callable[..., Dict[str, Any]]):
        _EXECUTORS[action_type] = fn
        return fn
    return _wrap


def get_executor(action_type: str) -> Optional[Callable[..., Dict[str, Any]]]:
    return _EXECUTORS.get(action_type)


# --------------------------------------------------------------------------- #
# Executors disponibles
# --------------------------------------------------------------------------- #
@register_executor("inventory.create_purchase_order")
def create_purchase_order(*, ai_action, user) -> Dict[str, Any]:
    """
    Crée un brouillon de PurchaseOrder à partir d'une AIAction
    ``inventory.create_purchase_order``. Le PO reste en DRAFT (l'humain doit
    encore le soumettre puis l'approuver via le viewset).
    """
    from datetime import date

    from inventory.models import (
        Article,
        PurchaseOrder,
        PurchaseOrderLine,
        PurchaseOrderStatus,
        Supplier,
        Warehouse,
    )

    payload = ai_action.payload or {}
    tenant = ai_action.tenant
    warehouse_id = payload.get("warehouse_id")
    supplier_id = payload.get("supplier_id")
    items = payload.get("items") or []

    if not warehouse_id:
        raise ValueError("warehouse_id manquant dans l'AIAction.")
    warehouse = Warehouse.objects.filter(tenant=tenant, id=warehouse_id).first()
    if warehouse is None:
        raise ValueError("Entrepôt introuvable.")

    supplier = None
    if supplier_id:
        supplier = Supplier.objects.filter(tenant=tenant, id=supplier_id).first()
    if supplier is None:
        # Tenant sans fournisseur : on échoue proprement.
        raise ValueError("Fournisseur cible non précisé — impossible de créer le BC.")

    order_number = f"PO-{date.today().isoformat()}-{str(ai_action.id)[:6].upper()}"
    po = PurchaseOrder.objects.create(
        tenant=tenant,
        order_number=order_number,
        supplier=supplier,
        warehouse=warehouse,
        order_date=date.today(),
        status=PurchaseOrderStatus.DRAFT,
        currency=getattr(supplier, "currency", "") or "XOF",
        notes=f"Brouillon généré par AIAction {ai_action.id}",
        requested_by=user if (user and user.is_authenticated) else None,
    )

    created_lines = 0
    for it in items:
        article = Article.objects.filter(tenant=tenant, id=it.get("article_id")).first()
        if article is None:
            continue
        PurchaseOrderLine.objects.create(
            tenant=tenant,
            purchase_order=po,
            article=article,
            description=it.get("name", "")[:200],
            quantity=it.get("recommended_qty") or 0,
            unit_price=it.get("estimated_unit_cost") or article.purchase_price,
        )
        created_lines += 1

    return {
        "purchase_order_id": str(po.id),
        "order_number": po.order_number,
        "status": po.status,
        "lines_count": created_lines,
    }


@register_executor("payroll.post_payroll_journal")
def post_payroll_journal(*, ai_action, user) -> Dict[str, Any]:
    """
    Génère une écriture comptable Finance à partir d'un PayrollJournal.

    Attendu dans payload :
        {"payroll_journal_id": "<uuid>"}

    L'écriture créée est en statut DRAFT — l'humain doit la POSTER manuellement.
    """
    from datetime import date

    from finance.models import (
        Account,
        AccountingPeriod,
        Journal,
        JournalEntry,
        JournalLine,
        MoveStatus,
    )
    from payroll.models import PayrollJournal

    payload = ai_action.payload or {}
    payroll_journal_id = payload.get("payroll_journal_id")
    if not payroll_journal_id:
        raise ValueError("payroll_journal_id manquant.")
    pj = PayrollJournal.objects.filter(
        tenant=ai_action.tenant, id=payroll_journal_id,
    ).select_related("period").first()
    if pj is None:
        raise ValueError("PayrollJournal introuvable.")

    target_date = pj.period.date_end or date.today()
    period = (
        AccountingPeriod.objects
        .filter(
            tenant=ai_action.tenant,
            date_start__lte=target_date,
            date_end__gte=target_date,
            status="OPEN",
        )
        .first()
    )
    if period is None:
        raise ValueError(f"Aucune période comptable OPEN pour {target_date}.")

    journal = (
        Journal.objects
        .filter(tenant=ai_action.tenant, is_active=True, type__in=["GENERAL", "BANK"])
        .order_by("-type")
        .first()
    )
    if journal is None:
        raise ValueError("Aucun journal comptable actif.")

    # Conventions OHADA simplifiées :
    # 6411 Charges salariales - Salaires bruts
    # 6311 Charges sociales patronales
    # 4421 État - IRPP retenue
    # 4311 CNPS à payer
    # 4711 Personnel - rémunérations dues
    code_to_account = {
        a.code: a
        for a in Account.objects.filter(
            tenant=ai_action.tenant,
            code__in=["6411", "6311", "4421", "4311", "4711"],
        )
    }
    missing = {"6411", "6311", "4421", "4311", "4711"} - set(code_to_account.keys())
    if missing:
        raise ValueError(
            f"Comptes manquants pour la passation paie : {sorted(missing)}. "
            "Initialisez le plan comptable."
        )

    entry = JournalEntry.objects.create(
        tenant=ai_action.tenant,
        journal=journal,
        period=period,
        entry_date=target_date,
        label=f"Paie {pj.period.label}",
        status=MoveStatus.DRAFT,
        source_model="payroll.PayrollJournal",
        source_object_id=str(pj.id),
    )

    # Débits
    JournalLine.objects.create(
        tenant=ai_action.tenant, entry=entry,
        account=code_to_account["6411"],
        label="Salaires bruts (charges)",
        debit=pj.total_gross, credit=0,
    )
    if pj.total_employer_charges:
        JournalLine.objects.create(
            tenant=ai_action.tenant, entry=entry,
            account=code_to_account["6311"],
            label="Charges patronales",
            debit=pj.total_employer_charges, credit=0,
        )

    # Crédits
    if pj.total_income_tax:
        JournalLine.objects.create(
            tenant=ai_action.tenant, entry=entry,
            account=code_to_account["4421"],
            label="IRPP retenu",
            debit=0, credit=pj.total_income_tax,
        )
    cnps_total = (pj.total_employer_charges or 0) + (
        pj.total_employee_deductions or 0
    ) - (pj.total_income_tax or 0)
    if cnps_total > 0:
        JournalLine.objects.create(
            tenant=ai_action.tenant, entry=entry,
            account=code_to_account["4311"],
            label="CNPS à payer",
            debit=0, credit=cnps_total,
        )
    if pj.total_net:
        JournalLine.objects.create(
            tenant=ai_action.tenant, entry=entry,
            account=code_to_account["4711"],
            label="Personnel - rémunérations dues",
            debit=0, credit=pj.total_net,
        )

    pj.is_posted = True
    pj.posted_at = ai_action.executed_at
    pj.journal_entry_id = str(entry.id)
    pj.save(update_fields=["is_posted", "posted_at", "journal_entry_id", "updated_at"])

    return {
        "journal_entry_id": str(entry.id),
        "payroll_journal_id": str(pj.id),
        "lines_count": entry.lines.count(),
        "status": entry.status,
    }


@register_executor("finance.post_journal_entry")
def post_journal_entry(*, ai_action, user) -> Dict[str, Any]:
    """
    Crée une JournalEntry + JournalLines à partir du payload de l'AIAction.

    Le payload doit contenir :
        {
          "label": str,
          "currency": str,
          "transaction_date": "YYYY-MM-DD",
          "lines": [
            {"account_code": "...", "debit": float, "credit": float, "label": "..."}
          ]
        }
    """
    from datetime import date

    from finance.models import (
        Account,
        AccountingPeriod,
        Journal,
        JournalEntry,
        JournalLine,
        MoveStatus,
    )

    payload = ai_action.payload or {}
    tenant = ai_action.tenant
    label = (payload.get("label") or "")[:255]
    currency = payload.get("currency") or "XOF"
    txn_date_str = payload.get("transaction_date")
    txn_date = date.fromisoformat(txn_date_str) if txn_date_str else date.today()
    lines_data = payload.get("lines") or []

    if not lines_data:
        raise ValueError("AIAction sans lignes d'écriture.")

    # Trouver la période ouverte qui couvre la date.
    period = (
        AccountingPeriod.objects
        .filter(
            tenant=tenant,
            date_start__lte=txn_date,
            date_end__gte=txn_date,
            status="OPEN",
        )
        .order_by("-date_start")
        .first()
    )
    if period is None:
        raise ValueError(f"Aucune période comptable OPEN pour {txn_date}.")

    # Choisir un journal "OD" (opérations diverses) par défaut.
    journal = (
        Journal.objects
        .filter(tenant=tenant, is_active=True, type__in=["GENERAL", "BANK", "CASH"])
        .order_by("-type")  # GENERAL en premier
        .first()
    )
    if journal is None:
        raise ValueError("Aucun journal actif disponible.")

    # Récupère les comptes par code.
    codes = {row.get("account_code") for row in lines_data if row.get("account_code")}
    accounts = {
        a.code: a
        for a in Account.objects.filter(tenant=tenant, code__in=codes)
    }
    missing = codes - set(accounts.keys())
    if missing:
        raise ValueError(f"Comptes inexistants : {', '.join(sorted(missing))}")

    # Vérifie l'équilibre.
    total_debit = sum(Decimal(str(r.get("debit") or 0)) for r in lines_data)
    total_credit = sum(Decimal(str(r.get("credit") or 0)) for r in lines_data)
    if total_debit != total_credit:
        raise ValueError(
            f"Écriture déséquilibrée (débit={total_debit}, crédit={total_credit})."
        )

    entry = JournalEntry.objects.create(
        tenant=tenant,
        journal=journal,
        period=period,
        entry_date=txn_date,
        label=label or "Écriture proposée par IA",
        status=MoveStatus.DRAFT,  # toujours en brouillon, l'humain "POSTERA" séparément
        source_model="ai_assistant.AIAction",
        source_object_id=str(ai_action.id),
    )

    for row in lines_data:
        JournalLine.objects.create(
            tenant=tenant,
            entry=entry,
            account=accounts[row["account_code"]],
            label=(row.get("label") or "")[:255],
            debit=Decimal(str(row.get("debit") or 0)),
            credit=Decimal(str(row.get("credit") or 0)),
            currency=currency,
            amount_currency=Decimal(str(row.get("debit") or row.get("credit") or 0)),
        )

    return {
        "journal_entry_id": str(entry.id),
        "journal": journal.code,
        "period": period.name,
        "lines_count": len(lines_data),
        "status": entry.status,
    }
