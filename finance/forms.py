"""
Formulaires Django du module Finance.

Stratégie :
- ``TenantModelForm`` injecte ``tenant`` automatiquement depuis la vue ;
  le champ ``tenant`` n'est jamais éditable.
- On utilise des ``exclude`` plutôt que ``fields="__all__"`` pour ne pas
  exposer les champs internes (audit, soft-delete, hash chain, idempotency,
  pdf_url, etc.).
"""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import (
    AuditEvent,
    CompanyFinanceProfile, FiscalYear, AccountingPeriod,
    Account, Journal, JournalEntry, JournalLine, Tax, FiscalClosing,
    ExchangeRate, Partner,
    Quote, QuoteLine, Invoice, InvoiceLine, Payment,
    SubscriptionPlan, Subscription, DunningStage, DunningEvent, CustomerPortalToken,
    VendorBill, VendorBillLine, ExpenseReport, ExpenseItem,
    PaymentOrder, PaymentOrderLine,
    BankConnector, BankAccount, BankTransaction, ReconciliationMatch,
    ReportSnapshot,
)


# Liste centralisée des champs internes à ne JAMAIS exposer côté formulaire.
INTERNAL_EXCLUDED_FIELDS = (
    "id",
    "tenant",            # injecté côté view
    "created_at",
    "updated_at",
    "is_deleted",
    "deleted_at",
    "event_hash",        # AuditEvent
    "prev_hash",
    "idempotency_key",   # Payment : clé d'idempotence générée côté serveur
    "provider_payload",  # secrets gateway
    "pdf_url",           # généré par le moteur PDF
)


class TenantModelForm(forms.ModelForm):
    """
    Formulaire de base : tenant injecté côté view (request.tenant) ; jamais
    éditable depuis l'UI. Les vues doivent passer ``tenant=request.tenant``
    via ``get_form_kwargs``.
    """

    class Meta:
        # Sécurité : par défaut on exclut les champs internes. Les sous-classes
        # peuvent surcharger ``exclude`` ou ``fields`` (mais ne devraient JAMAIS
        # mettre ``fields = "__all__"``).
        exclude = INTERNAL_EXCLUDED_FIELDS

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if "tenant" in self.fields:  # protection si une sous-classe le rajoute
            self.fields["tenant"].disabled = True
            self.fields["tenant"].required = False

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.tenant and hasattr(obj, "tenant_id") and not obj.tenant_id:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            self.save_m2m()
        return obj


# ===========================================================================
# SIMPLE MODEL FORMS
# ===========================================================================
class CompanyFinanceProfileForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = CompanyFinanceProfile


class FiscalYearForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = FiscalYear


class AccountingPeriodForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = AccountingPeriod


class AccountForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Account


class JournalForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Journal


class TaxForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Tax


class FiscalClosingForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = FiscalClosing
        # Les références d'écritures de clôture sont posées par le service
        # métier, pas par l'utilisateur final.
        exclude = INTERNAL_EXCLUDED_FIELDS + (
            "closing_entry",
            "opening_entry_next_fy",
            "generated_at",
            "posted_at",
        )


class ExchangeRateForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = ExchangeRate


class PartnerForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Partner


class PaymentForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Payment
        # Le journal_entry_id et le provider_payload sont posés par les
        # webhooks/gateways, jamais par l'utilisateur.
        exclude = INTERNAL_EXCLUDED_FIELDS + (
            "journal_entry_id",
            "provider_payload",
        )


class SubscriptionPlanForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = SubscriptionPlan


class SubscriptionForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Subscription


class DunningStageForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = DunningStage


class DunningEventForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = DunningEvent


class CustomerPortalTokenForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = CustomerPortalToken


class VendorBillForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = VendorBill


class ExpenseReportForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = ExpenseReport


class PaymentOrderForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = PaymentOrder


class BankConnectorForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = BankConnector


class BankAccountForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = BankAccount


class BankTransactionForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = BankTransaction


class ReconciliationMatchForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = ReconciliationMatch


class ReportSnapshotForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = ReportSnapshot


class JournalEntryForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = JournalEntry
        # Liens vers les objets sources sont posés par les services métier,
        # pas saisissables par l'utilisateur.
        exclude = INTERNAL_EXCLUDED_FIELDS + (
            "source_model",
            "source_object_id",
        )


class QuoteForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Quote


class InvoiceForm(TenantModelForm):
    class Meta(TenantModelForm.Meta):
        model = Invoice


# ===========================================================================
# FORMSETS LIGNES
# ===========================================================================
JournalLineFormSet = inlineformset_factory(
    JournalEntry,
    JournalLine,
    fields=("account", "partner_label", "label", "debit", "credit", "currency", "amount_currency"),
    extra=1,
    can_delete=True,
)

QuoteLineFormSet = inlineformset_factory(
    Quote,
    QuoteLine,
    fields=("label", "quantity", "unit_price", "tax"),
    extra=1,
    can_delete=True,
)

InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    fields=("label", "quantity", "unit_price", "tax"),
    extra=1,
    can_delete=True,
)

VendorBillLineFormSet = inlineformset_factory(
    VendorBill,
    VendorBillLine,
    fields=("label", "quantity", "unit_price", "tax", "expense_account_code"),
    extra=1,
    can_delete=True,
)

ExpenseItemFormSet = inlineformset_factory(
    ExpenseReport,
    ExpenseItem,
    fields=("date", "label", "category", "amount", "currency", "tax", "receipt"),
    extra=1,
    can_delete=True,
)

PaymentOrderLineFormSet = inlineformset_factory(
    PaymentOrder,
    PaymentOrderLine,
    fields=("bill", "amount", "currency", "beneficiary_name", "beneficiary_iban", "beneficiary_bic", "reference"),
    extra=1,
    can_delete=True,
)
