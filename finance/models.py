from __future__ import annotations

import secrets
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

# Create your models here.
# compliance/models.py
import hashlib
import json
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from finance.models_base import TenantOwnedModel, UUIDPkModel, Currency


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    POST = "POST", "Post"
    REVERSE = "REVERSE", "Reverse"
    LOCK = "LOCK", "Lock"
    UNLOCK = "UNLOCK", "Unlock"
    CLOSE = "CLOSE", "Close"
    SYNC = "SYNC", "Sync"
    IMPORT = "IMPORT", "Import"
    EXPORT = "EXPORT", "Export"
    LOGIN = "LOGIN", "Login"
    OTHER = "OTHER", "Other"


class AuditEvent(UUIDPkModel, TenantOwnedModel):
    """
    Piste d'audit fiable : hash chain (type blockchain léger) pour détecter toute altération.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events"
    )

    action = models.CharField(max_length=12, choices=AuditAction.choices, db_index=True)
    model_label = models.CharField(max_length=128, db_index=True)  # ex: "billing.Invoice"
    object_id = models.CharField(max_length=64, db_index=True)  # UUID ou int string
    object_repr = models.CharField(max_length=255, blank=True)

    # Avant / Après (diff)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    # Métadonnées: ip, user_agent, source ("UI", "API", "CELERY", "BANK_SYNC", "OCR"), correlation_id...
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Hash chain
    prev_hash = models.CharField(max_length=64, blank=True, db_index=True)
    event_hash = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "model_label", "object_id"]),
            models.Index(fields=["tenant", "action"]),
        ]

    def compute_hash(self) -> str:
        payload = {
            "tenant_id": str(self.tenant_id),
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "action": self.action,
            "model_label": self.model_label,
            "object_id": self.object_id,
            "before": self.before,
            "after": self.after,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "prev_hash": self.prev_hash,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def save(self, *args, **kwargs):
        if not self.event_hash:
            # event_hash final seulement quand created_at est défini (après insert) => fallback
            pass
        super().save(*args, **kwargs)
        if not self.event_hash:
            self.event_hash = self.compute_hash()
            super().save(update_fields=["event_hash"])


class AccountingStandard(models.TextChoices):
    SYSCOHADA = "SYSCOHADA", "SYSCOHADA"
    PCG = "PCG", "PCG (France)"
    IFRS = "IFRS", "IFRS"
    CUSTOM = "CUSTOM", "Custom"


class CompanyFinanceProfile(UUIDPkModel, TenantOwnedModel):
    """
    Paramètres finance par tenant : devise, standard, comptes par défaut, etc.
    """
    base_currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    standard = models.CharField(max_length=12, choices=AccountingStandard.choices, default=AccountingStandard.SYSCOHADA)

    # Paramètres numérotation
    invoice_prefix = models.CharField(max_length=20, default="INV")
    bill_prefix = models.CharField(max_length=20, default="BILL")
    quote_prefix = models.CharField(max_length=20, default="QT")

    # Options
    lock_posted_entries = models.BooleanField(default=True)
    require_attachments_for_expenses = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_fin_profile_per_tenant"),
        ]


class FiscalYear(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=64)  # ex: FY2026
    date_start = models.DateField()
    date_end = models.DateField()
    is_closed = models.BooleanField(default=False, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(date_end__gte=models.F("date_start")), name="fy_dates_ok"),
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_fy_name_per_tenant"),
        ]
        indexes = [models.Index(fields=["tenant", "is_closed"])]

    def __str__(self):
        return self.name


class PeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    LOCKED = "LOCKED", "Verrouillée"
    CLOSED = "CLOSED", "Clôturée"


class AccountingPeriod(UUIDPkModel, TenantOwnedModel):
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name="periods")
    name = models.CharField(max_length=64)  # ex: 2026-01
    date_start = models.DateField()
    date_end = models.DateField()
    status = models.CharField(max_length=10, choices=PeriodStatus.choices, default=PeriodStatus.OPEN, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(date_end__gte=models.F("date_start")), name="period_dates_ok"),
            models.UniqueConstraint(fields=["tenant", "fiscal_year", "name"], name="uniq_period_name"),
        ]
        indexes = [
            models.Index(fields=["tenant", "fiscal_year"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return self.name


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Actif"
    LIABILITY = "LIABILITY", "Passif"
    EQUITY = "EQUITY", "Capitaux"
    REVENUE = "REVENUE", "Produits"
    EXPENSE = "EXPENSE", "Charges"


class Account(UUIDPkModel, TenantOwnedModel):
    """
    Plan comptable personnalisable (SYSCOHADA, PCG, IFRS, custom).
    """
    code = models.CharField(max_length=32)  # ex: 512, 411, 401, 606...
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=12, choices=AccountType.choices, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    is_reconcilable = models.BooleanField(default=False)  # utile pour 401/411/512
    allow_manual = models.BooleanField(default=True)  # certains comptes peuvent être verrouillés

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_account_code"),
        ]
        indexes = [
            models.Index(fields=["tenant", "code"]),
            models.Index(fields=["tenant", "type"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalType(models.TextChoices):
    SALES = "SALES", "Ventes"
    PURCHASE = "PURCHASE", "Achats"
    BANK = "BANK", "Banque"
    CASH = "CASH", "Caisse"
    GENERAL = "GENERAL", "Opérations diverses"


class Journal(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=20)  # ex: VT, AC, BQ, CS, OD
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=12, choices=JournalType.choices, default=JournalType.GENERAL, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    default_debit_account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="journals_default_debit"
    )
    default_credit_account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="journals_default_credit"
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uniq_journal_code")]
        indexes = [
            models.Index(fields=["tenant", "type"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class MoveStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    POSTED = "POSTED", "Comptabilisée"
    CANCELLED = "CANCELLED", "Annulée"


class JournalEntry(UUIDPkModel, TenantOwnedModel):
    """
    Écriture comptable (pièce).
    """
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="entries")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="entries")
    entry_date = models.DateField(default=timezone.now, db_index=True)

    reference = models.CharField(max_length=80, blank=True, db_index=True)  # ex: INV-2026-0001
    label = models.CharField(max_length=255)

    status = models.CharField(max_length=10, choices=MoveStatus.choices, default=MoveStatus.DRAFT, db_index=True)

    # Liens facultatifs vers objets sources (facture, paiement, etc.) sans FK directe (évite dépendances circulaires)
    source_model = models.CharField(max_length=128, blank=True)  # ex: "billing.Invoice"
    source_object_id = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "entry_date"]),
            models.Index(fields=["tenant", "reference"]),
        ]

    @property
    def total_debit(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("debit"))["s"] or Decimal("0")

    @property
    def total_credit(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("credit"))["s"] or Decimal("0")

    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class JournalLine(UUIDPkModel, TenantOwnedModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")

    partner_label = models.CharField(max_length=160, blank=True)  # utile pour 411/401 (facultatif)
    label = models.CharField(max_length=255, blank=True)

    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    # multi-devises : montant en devise d'origine (optionnel si GL est en base_currency)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    amount_currency = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                        (Q(debit__gt=0) & Q(credit=0)) |
                        (Q(credit__gt=0) & Q(debit=0)) |
                        (Q(credit=0) & Q(debit=0))
                ),
                name="line_debit_or_credit_only",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"]),
            models.Index(fields=["tenant", "currency"]),
        ]


class TaxScope(models.TextChoices):
    SALES = "SALES", "TVA collectée"
    PURCHASE = "PURCHASE", "TVA déductible"
    BOTH = "BOTH", "Les deux"


class Tax(UUIDPkModel, TenantOwnedModel):
    """
    Gestion TVA : taux + comptes de TVA collectée/déductible
    """
    name = models.CharField(max_length=80)  # ex: TVA 18%
    rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])  # 18.00
    scope = models.CharField(max_length=10, choices=TaxScope.choices, default=TaxScope.BOTH)

    is_active = models.BooleanField(default=True, db_index=True)

    # Comptes associés (optionnels mais recommandés)
    sales_tax_account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="tax_sales"
    )
    purchase_tax_account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="tax_purchase"
    )

    class Meta:
        indexes = [models.Index(fields=["tenant", "is_active"]), models.Index(fields=["tenant", "scope"])]

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class ClosingStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    GENERATED = "GENERATED", "Généré"
    POSTED = "POSTED", "Comptabilisé"


class FiscalClosing(UUIDPkModel, TenantOwnedModel):
    """
    Clôture d'exercice : contient références vers écritures de clôture (bilan/CR/report à nouveau).
    """
    fiscal_year = models.OneToOneField(FiscalYear, on_delete=models.PROTECT, related_name="closing")
    status = models.CharField(max_length=12, choices=ClosingStatus.choices, default=ClosingStatus.DRAFT, db_index=True)

    generated_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    closing_entry = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="as_closing_entry"
    )
    opening_entry_next_fy = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="as_opening_entry"
    )

    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status"])]


class ExchangeRate(UUIDPkModel, TenantOwnedModel):
    """
    Taux de change par date.
    - base_currency: devise société
    - quote_currency: devise étrangère
    - rate: 1 base = rate quote ? ou inverse ? -> on fixe une convention:
      Convention: 1 quote_currency = rate * base_currency (plus simple pour convertir vers base)
    """
    date = models.DateField(db_index=True)

    base_currency = models.CharField(max_length=3, choices=Currency.choices)
    quote_currency = models.CharField(max_length=3, choices=Currency.choices)

    # 1 quote = rate base (ex: 1 USD = 600 XOF => rate=600 si base=XOF, quote=USD)
    rate = models.DecimalField(max_digits=18, decimal_places=8, validators=[MinValueValidator(0)])

    source = models.CharField(max_length=80, blank=True)  # ex: "ECB", "Manual"
    is_locked = models.BooleanField(default=False, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=~Q(base_currency=models.F("quote_currency")), name="fx_currencies_diff"),
            models.UniqueConstraint(
                fields=["tenant", "date", "base_currency", "quote_currency"],
                name="uniq_fx_rate_per_day"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "date"]),
            models.Index(fields=["tenant", "base_currency", "quote_currency"]),
        ]


class PartnerType(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Client"
    SUPPLIER = "SUPPLIER", "Fournisseur"
    BOTH = "BOTH", "Client & Fournisseur"


class Partner(UUIDPkModel, TenantOwnedModel):
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=160)
    type = models.CharField(max_length=10, choices=PartnerType.choices, default=PartnerType.CUSTOMER, db_index=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    vat_number = models.CharField(max_length=40, blank=True)  # N° TVA / CC
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_partner_code"),
        ]
        indexes = [
            models.Index(fields=["tenant", "type"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class DocumentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    SENT = "SENT", "Envoyé"
    ACCEPTED = "ACCEPTED", "Accepté"
    REJECTED = "REJECTED", "Rejeté"
    CANCELLED = "CANCELLED", "Annulé"




class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    ISSUED = "ISSUED", "Émise"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partiellement payée"
    PAID = "PAID", "Payée"
    OVERDUE = "OVERDUE", "En retard"
    CANCELLED = "CANCELLED", "Annulée"


class InvoiceType(models.TextChoices):
    SALE = "SALE", "Vente"


class Quote(UUIDPkModel, TenantOwnedModel):
    number = models.CharField(max_length=40, db_index=True)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="quotes")
    status = models.CharField(max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT,
                              db_index=True)

    issue_date = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)

    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    notes = models.TextField(blank=True)

    # PDF
    pdf_file = models.FileField(upload_to="billing/quotes/%Y/%m/", blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="uniq_quote_number")]
        indexes = [models.Index(fields=["tenant", "status"]), models.Index(fields=["tenant", "issue_date"])]

    def subtotal(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("line_total"))["s"] or Decimal("0")

    def total_tax(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("tax_amount"))["s"] or Decimal("0")

    def total(self) -> Decimal:
        return self.subtotal() + self.total_tax()


class QuoteLine(UUIDPkModel, TenantOwnedModel):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    label = models.CharField(max_length=255)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        base = (self.quantity or 0) * (self.unit_price or 0)
        self.line_total = base
        rate = (self.tax.rate if self.tax else Decimal("0")) / Decimal("100")
        self.tax_amount = (base * rate).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Invoice(UUIDPkModel, TenantOwnedModel):
    type = models.CharField(max_length=10, choices=InvoiceType.choices, default=InvoiceType.SALE)
    number = models.CharField(max_length=40, db_index=True)

    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True)

    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True, db_index=True)

    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    notes = models.TextField(blank=True)

    # lien vers devis (optionnel)
    quote = models.ForeignKey(Quote, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")

    # PDF + email tracking
    pdf_file = models.FileField(upload_to="billing/invoices/%Y/%m/", blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # locking (évite edits concurrents / paiement lock)
    lock_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice_locks"
    )
    lock_at = models.DateTimeField(null=True, blank=True)

    # lien vers écriture comptable (OneToOne dans accounting via id stocké en string pour éviter circular import)
    journal_entry_id = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="uniq_invoice_number")]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "issue_date"]),
            models.Index(fields=["tenant", "due_date"]),
        ]

    def subtotal(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("line_total"))["s"] or Decimal("0")

    def total_tax(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("tax_amount"))["s"] or Decimal("0")

    def total(self) -> Decimal:
        return self.subtotal() + self.total_tax()

    def amount_paid(self) -> Decimal:
        return self.payments.filter(status=PaymentStatus.DONE).aggregate(s=models.Sum("amount"))["s"] or Decimal("0")

    def amount_due(self) -> Decimal:
        due = self.total() - self.amount_paid()
        return due if due > 0 else Decimal("0")


class InvoiceLine(UUIDPkModel, TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    label = models.CharField(max_length=255)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        base = (self.quantity or 0) * (self.unit_price or 0)
        self.line_total = base
        rate = (self.tax.rate if self.tax else Decimal("0")) / Decimal("100")
        self.tax_amount = (base * rate).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Espèces"
    BANK = "BANK", "Banque"
    MOBILE = "MOBILE", "Mobile money"
    CHEQUE = "CHEQUE", "Chèque"
    CARD = "CARD", "Carte"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    DONE = "DONE", "Effectué"
    FAILED = "FAILED", "Échoué"
    CANCELLED = "CANCELLED", "Annulé"


class Payment(UUIDPkModel, TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")

    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING,
                              db_index=True)

    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)

    paid_at = models.DateTimeField(default=timezone.now, db_index=True)
    reference = models.CharField(max_length=120, blank=True)  # ref mobile money / bank ref / etc

    # gateway online
    provider = models.CharField(max_length=40, blank=True)  # stripe, paydunya, cinetpay...
    provider_payload = models.JSONField(default=dict, blank=True)

    journal_entry_id = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "paid_at"]),
            models.Index(fields=["tenant", "provider"]),
        ]


class RecurrenceUnit(models.TextChoices):
    DAY = "DAY", "Jour"
    WEEK = "WEEK", "Semaine"
    MONTH = "MONTH", "Mois"
    YEAR = "YEAR", "Année"


class SubscriptionPlan(UUIDPkModel, TenantOwnedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])

    interval_unit = models.CharField(max_length=8, choices=RecurrenceUnit.choices, default=RecurrenceUnit.MONTH)
    interval_count = models.PositiveIntegerField(default=1)  # every 1 month, 12 months, etc.

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "is_active"])]


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Suspendue"
    CANCELLED = "CANCELLED", "Annulée"
    ENDED = "ENDED", "Terminée"


class Subscription(UUIDPkModel, TenantOwnedModel):
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")

    status = models.CharField(max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE,
                              db_index=True)

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    next_invoice_date = models.DateField(null=True, blank=True, db_index=True)
    last_invoiced_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "next_invoice_date"]),
        ]


class DunningStage(UUIDPkModel, TenantOwnedModel):
    """
    Étapes de relance : J+3, J+10, J+20 ...
    """
    name = models.CharField(max_length=80)
    days_after_due = models.PositiveIntegerField()  # ex: 3
    email_subject = models.CharField(max_length=160)
    email_body = models.TextField()

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "days_after_due"], name="uniq_dunning_day"),
        ]
        indexes = [models.Index(fields=["tenant", "is_active"])]


class DunningEvent(UUIDPkModel, TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="dunning_events")
    stage = models.ForeignKey(DunningStage, on_delete=models.PROTECT, related_name="events")

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    channel = models.CharField(max_length=20, default="EMAIL")
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "invoice", "stage"], name="uniq_dunning_once"),
        ]
        indexes = [models.Index(fields=["tenant", "sent_at"])]


class CustomerPortalToken(UUIDPkModel, TenantOwnedModel):
    """
    Accès portail via token (si tu ne crées pas un user client).
    """
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="portal_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class VendorBillStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    OCR_EXTRACTED = "OCR_EXTRACTED", "OCR extrait"
    VALIDATED = "VALIDATED", "Validée"
    POSTED = "POSTED", "Comptabilisée"
    PAID = "PAID", "Payée"
    CANCELLED = "CANCELLED", "Annulée"


class VendorBill(UUIDPkModel, TenantOwnedModel):
    number = models.CharField(max_length=40, db_index=True)
    supplier = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="vendor_bills")
    status = models.CharField(max_length=14, choices=VendorBillStatus.choices, default=VendorBillStatus.DRAFT,
                              db_index=True)

    bill_date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)

    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    notes = models.TextField(blank=True)

    # Document + OCR
    document = models.FileField(upload_to="purchasing/vendor_bills/%Y/%m/", blank=True)
    ocr_text = models.TextField(blank=True)
    ocr_json = models.JSONField(default=dict, blank=True)  # résultat brut IA
    parsed_json = models.JSONField(default=dict, blank=True)  # proposition de champs/lignes

    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="validated_bills")
    validated_at = models.DateTimeField(null=True, blank=True)

    journal_entry_id = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="uniq_vendor_bill_number")]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "bill_date"]),
            models.Index(fields=["tenant", "due_date"]),
        ]

    def subtotal(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("line_total"))["s"] or Decimal("0")

    def total_tax(self) -> Decimal:
        return self.lines.aggregate(s=models.Sum("tax_amount"))["s"] or Decimal("0")

    def total(self) -> Decimal:
        return self.subtotal() + self.total_tax()


class VendorBillLine(UUIDPkModel, TenantOwnedModel):
    bill = models.ForeignKey(VendorBill, on_delete=models.CASCADE, related_name="lines")
    label = models.CharField(max_length=255)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    expense_account_code = models.CharField(max_length=32, blank=True)  # mapping flexible vers compte 60x/61x etc.

    def save(self, *args, **kwargs):
        base = (self.quantity or 0) * (self.unit_price or 0)
        self.line_total = base
        rate = (self.tax.rate if self.tax else Decimal("0")) / Decimal("100")
        self.tax_amount = (base * rate).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class ExpenseReportStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    SUBMITTED = "SUBMITTED", "Soumis"
    MANAGER_APPROVED = "MANAGER_APPROVED", "Validé manager"
    FINANCE_APPROVED = "FINANCE_APPROVED", "Validé finance"
    REJECTED = "REJECTED", "Rejeté"
    PAID = "PAID", "Payé"
    POSTED = "POSTED", "Comptabilisé"


class ExpenseReport(UUIDPkModel, TenantOwnedModel):
    employee_id = models.CharField(max_length=64, blank=True, db_index=True)  # lien RH (évite circular import)
    title = models.CharField(max_length=160)
    status = models.CharField(max_length=18, choices=ExpenseReportStatus.choices, default=ExpenseReportStatus.DRAFT,
                              db_index=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name="expense_manager_approvals")
    approved_by_finance = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name="expense_finance_approvals")

    notes = models.TextField(blank=True)
    journal_entry_id = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status"]), models.Index(fields=["tenant", "employee_id"])]


class ExpenseItem(UUIDPkModel, TenantOwnedModel):
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="items")

    date = models.DateField(default=timezone.now, db_index=True)
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=80, blank=True)

    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])

    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)

    receipt = models.FileField(upload_to="purchasing/expenses/%Y/%m/", blank=True)
    ocr_text = models.TextField(blank=True)
    ocr_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "date"]), models.Index(fields=["tenant", "category"])]


class PaymentOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    GENERATED = "GENERATED", "Fichier généré"
    SENT = "SENT", "Envoyé"
    CONFIRMED = "CONFIRMED", "Confirmé"
    CANCELLED = "CANCELLED", "Annulé"


class PaymentOrder(UUIDPkModel, TenantOwnedModel):
    """
    Lot de paiements fournisseurs (SEPA pain.001) ou autres formats.
    """
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=PaymentOrderStatus.choices, default=PaymentOrderStatus.DRAFT,
                              db_index=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    generated_file = models.FileField(upload_to="purchasing/payment_orders/%Y/%m/", blank=True)

    meta = models.JSONField(default=dict, blank=True)  # iban debiteur, bank, etc.
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status"])]


class PaymentOrderLine(UUIDPkModel, TenantOwnedModel):
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="lines")
    bill = models.ForeignKey(VendorBill, on_delete=models.PROTECT, related_name="payment_order_lines")

    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)

    beneficiary_name = models.CharField(max_length=160)
    beneficiary_iban = models.CharField(max_length=64, blank=True)
    beneficiary_bic = models.CharField(max_length=32, blank=True)

    reference = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "order", "bill"], name="uniq_bill_once_in_order"),
        ]
        indexes = [models.Index(fields=["tenant", "currency"])]


class BankProvider(models.TextChoices):
    MANUAL = "MANUAL", "Manual/CSV"
    BRIDGE = "BRIDGE", "Bridge"
    TINK = "TINK", "Tink"


class BankConnector(UUIDPkModel, TenantOwnedModel):
    provider = models.CharField(max_length=12, choices=BankProvider.choices, default=BankProvider.MANUAL)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True, db_index=True)

    # credentials chiffrées (à gérer via django-cryptography ou champ chiffré maison)
    credentials = models.JSONField(default=dict, blank=True)

    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "provider"]), models.Index(fields=["tenant", "is_active"])]


class BankAccount(UUIDPkModel, TenantOwnedModel):
    connector = models.ForeignKey(BankConnector, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="accounts")

    name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)

    iban = models.CharField(max_length=64, blank=True)
    bic = models.CharField(max_length=32, blank=True)

    external_id = models.CharField(max_length=128, blank=True, db_index=True)  # id banque/provider
    is_active = models.BooleanField(default=True, db_index=True)

    # lien vers compte comptable 512 (banque)
    gl_account_code = models.CharField(max_length=32, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "external_id"], name="uniq_bank_account_external",
                                    condition=~Q(external_id="")),
        ]
        indexes = [
            models.Index(fields=["tenant", "currency"]),
            models.Index(fields=["tenant", "is_active"]),
        ]


class BankTxnStatus(models.TextChoices):
    IMPORTED = "IMPORTED", "Importé"
    MATCHED = "MATCHED", "Rapproché"
    IGNORED = "IGNORED", "Ignoré"


class BankTransaction(UUIDPkModel, TenantOwnedModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField(db_index=True)

    label = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # positif=entrée, négatif=sortie
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XOF)

    external_id = models.CharField(max_length=128, blank=True, db_index=True)  # idempotence sync
    raw = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=10, choices=BankTxnStatus.choices, default=BankTxnStatus.IMPORTED,
                              db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "bank_account", "external_id"],
                name="uniq_bank_txn_external",
                condition=~Q(external_id="")
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "date"]),
            models.Index(fields=["tenant", "status"]),
        ]


class ReconciliationType(models.TextChoices):
    INVOICE_PAYMENT = "INVOICE_PAYMENT", "Paiement facture client"
    VENDOR_PAYMENT = "VENDOR_PAYMENT", "Paiement fournisseur"
    OTHER = "OTHER", "Autre"


class ReconciliationMatch(UUIDPkModel, TenantOwnedModel):
    """
    Match entre mouvement bancaire et pièce (facture/paiement/bill/...).
    On stocke des références textuelles pour éviter dépendances circulaires.
    """
    bank_transaction = models.OneToOneField(BankTransaction, on_delete=models.CASCADE, related_name="match")

    match_type = models.CharField(max_length=20, choices=ReconciliationType.choices, default=ReconciliationType.OTHER)

    target_model = models.CharField(max_length=128, blank=True)  # ex: "billing.Payment"
    target_object_id = models.CharField(max_length=64, blank=True)

    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # score 0..100
    matched_at = models.DateTimeField(auto_now_add=True)

    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "matched_at"]), models.Index(fields=["tenant", "match_type"])]


class ReportType(models.TextChoices):
    TRIAL_BALANCE = "TRIAL_BALANCE", "Balance"
    GENERAL_LEDGER = "GENERAL_LEDGER", "Grand livre"
    VAT_REPORT = "VAT_REPORT", "TVA"
    BALANCE_SHEET = "BALANCE_SHEET", "Bilan"
    PROFIT_LOSS = "PROFIT_LOSS", "Compte de résultat"
    CASH_FORECAST = "CASH_FORECAST", "Prévision trésorerie"
    AGED_AR = "AGED_AR", "Balance âgée clients"
    AGED_AP = "AGED_AP", "Balance âgée fournisseurs"


class ReportSnapshot(UUIDPkModel, TenantOwnedModel):
    """
    Stocke le résultat d'un rapport (JSON) + fichier export (PDF/CSV/XLSX).
    """
    report_type = models.CharField(max_length=24, choices=ReportType.choices, db_index=True)

    # Paramètres de génération (période, comptes, filtres)
    params = models.JSONField(default=dict, blank=True)

    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    generated_by_id = models.CharField(max_length=64, blank=True)

    # résultat (données)
    data = models.JSONField(default=dict, blank=True)

    # export
    file = models.FileField(upload_to="reporting/%Y/%m/", blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "report_type"]),
            models.Index(fields=["tenant", "generated_at"]),
        ]
