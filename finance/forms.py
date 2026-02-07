# finance/forms.py
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


class TenantModelForm(forms.ModelForm):
    """
    Le tenant est injecté côté view (request.tenant) -> jamais editable en UI.
    """
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if "tenant" in self.fields:
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


# ========== SIMPLE MODEL FORMS ==========
class CompanyFinanceProfileForm(TenantModelForm):
    class Meta:
        model = CompanyFinanceProfile
        fields = "__all__"


class FiscalYearForm(TenantModelForm):
    class Meta:
        model = FiscalYear
        fields = "__all__"


class AccountingPeriodForm(TenantModelForm):
    class Meta:
        model = AccountingPeriod
        fields = "__all__"


class AccountForm(TenantModelForm):
    class Meta:
        model = Account
        fields = "__all__"


class JournalForm(TenantModelForm):
    class Meta:
        model = Journal
        fields = "__all__"


class TaxForm(TenantModelForm):
    class Meta:
        model = Tax
        fields = "__all__"


class FiscalClosingForm(TenantModelForm):
    class Meta:
        model = FiscalClosing
        fields = "__all__"


class ExchangeRateForm(TenantModelForm):
    class Meta:
        model = ExchangeRate
        fields = "__all__"


class PartnerForm(TenantModelForm):
    class Meta:
        model = Partner
        fields = "__all__"


class PaymentForm(TenantModelForm):
    class Meta:
        model = Payment
        fields = "__all__"


class SubscriptionPlanForm(TenantModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"


class SubscriptionForm(TenantModelForm):
    class Meta:
        model = Subscription
        fields = "__all__"


class DunningStageForm(TenantModelForm):
    class Meta:
        model = DunningStage
        fields = "__all__"


class DunningEventForm(TenantModelForm):
    class Meta:
        model = DunningEvent
        fields = "__all__"


class CustomerPortalTokenForm(TenantModelForm):
    class Meta:
        model = CustomerPortalToken
        fields = "__all__"


class VendorBillForm(TenantModelForm):
    class Meta:
        model = VendorBill
        fields = "__all__"


class ExpenseReportForm(TenantModelForm):
    class Meta:
        model = ExpenseReport
        fields = "__all__"


class PaymentOrderForm(TenantModelForm):
    class Meta:
        model = PaymentOrder
        fields = "__all__"


class BankConnectorForm(TenantModelForm):
    class Meta:
        model = BankConnector
        fields = "__all__"


class BankAccountForm(TenantModelForm):
    class Meta:
        model = BankAccount
        fields = "__all__"


class BankTransactionForm(TenantModelForm):
    class Meta:
        model = BankTransaction
        fields = "__all__"


class ReconciliationMatchForm(TenantModelForm):
    class Meta:
        model = ReconciliationMatch
        fields = "__all__"


class ReportSnapshotForm(TenantModelForm):
    class Meta:
        model = ReportSnapshot
        fields = "__all__"


# ========== MASTER + LINES FORMS ==========
class JournalEntryForm(TenantModelForm):
    class Meta:
        model = JournalEntry
        fields = "__all__"


JournalLineFormSet = inlineformset_factory(
    JournalEntry,
    JournalLine,
    fields=("account", "partner_label", "label", "debit", "credit", "currency", "amount_currency"),
    extra=1,
    can_delete=True,
)


class QuoteForm(TenantModelForm):
    class Meta:
        model = Quote
        fields = "__all__"


QuoteLineFormSet = inlineformset_factory(
    Quote,
    QuoteLine,
    fields=("label", "quantity", "unit_price", "tax"),
    extra=1,
    can_delete=True,
)


class InvoiceForm(TenantModelForm):
    class Meta:
        model = Invoice
        fields = "__all__"


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