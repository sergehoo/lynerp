# finance/api/serializers.py
from django.urls import reverse
from rest_framework import serializers
from finance.models import (
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

# -------- Helpers
class TenantReadOnlyMixin(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)


# -------- Core
class AuditEventSerializer(TenantReadOnlyMixin):
    class Meta:
        model = AuditEvent
        fields = "__all__"
        read_only_fields = ("id", "tenant", "created_at", "event_hash")


class CompanyFinanceProfileSerializer(TenantReadOnlyMixin):
    class Meta:
        model = CompanyFinanceProfile
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class FiscalYearSerializer(TenantReadOnlyMixin):
    class Meta:
        model = FiscalYear
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class AccountingPeriodSerializer(TenantReadOnlyMixin):
    class Meta:
        model = AccountingPeriod
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class AccountSerializer(TenantReadOnlyMixin):
    class Meta:
        model = Account
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class JournalSerializer(TenantReadOnlyMixin):
    class Meta:
        model = Journal
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class JournalLineSerializer(TenantReadOnlyMixin):
    class Meta:
        model = JournalLine
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class JournalEntrySerializer(TenantReadOnlyMixin):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class TaxSerializer(TenantReadOnlyMixin):
    class Meta:
        model = Tax
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class FiscalClosingSerializer(TenantReadOnlyMixin):
    class Meta:
        model = FiscalClosing
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class ExchangeRateSerializer(TenantReadOnlyMixin):
    class Meta:
        model = ExchangeRate
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class PartnerSerializer(TenantReadOnlyMixin):
    class Meta:
        model = Partner
        fields = "__all__"
        read_only_fields = ("id", "tenant")


# -------- Sales docs
class QuoteLineSerializer(TenantReadOnlyMixin):
    class Meta:
        model = QuoteLine
        fields = "__all__"
        read_only_fields = ("id", "tenant", "line_total", "tax_amount")


class QuoteSerializer(TenantReadOnlyMixin):
    pdf_url = serializers.SerializerMethodField()

    lines = QuoteLineSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source="partner.name", read_only=True)


    def get_pdf_url(self, obj):
        request = self.context.get("request")
        url = reverse("finance:quote_pdf", args=[obj.id])
        return request.build_absolute_uri(url) if request else url
    class Meta:
        model = Quote
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class InvoiceLineSerializer(TenantReadOnlyMixin):
    class Meta:
        model = InvoiceLine
        fields = "__all__"
        read_only_fields = ("id", "tenant", "line_total", "tax_amount")


class InvoiceSerializer(TenantReadOnlyMixin):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source="partner.name", read_only=True)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class PaymentSerializer(TenantReadOnlyMixin):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    customer_name = serializers.CharField(source="invoice.partner.name", read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("id", "tenant")


# -------- Subscriptions & dunning
class SubscriptionPlanSerializer(TenantReadOnlyMixin):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class SubscriptionSerializer(TenantReadOnlyMixin):
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Subscription
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class DunningStageSerializer(TenantReadOnlyMixin):
    class Meta:
        model = DunningStage
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class DunningEventSerializer(TenantReadOnlyMixin):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = DunningEvent
        fields = "__all__"
        read_only_fields = ("id", "tenant", "sent_at")


class CustomerPortalTokenSerializer(TenantReadOnlyMixin):
    partner_name = serializers.CharField(source="partner.name", read_only=True)

    class Meta:
        model = CustomerPortalToken
        fields = "__all__"
        read_only_fields = ("id", "tenant", "token")


# -------- Purchases
class VendorBillLineSerializer(TenantReadOnlyMixin):
    class Meta:
        model = VendorBillLine
        fields = "__all__"
        read_only_fields = ("id", "tenant", "line_total", "tax_amount")


class VendorBillSerializer(TenantReadOnlyMixin):
    lines = VendorBillLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = VendorBill
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class ExpenseItemSerializer(TenantReadOnlyMixin):
    class Meta:
        model = ExpenseItem
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class ExpenseReportSerializer(TenantReadOnlyMixin):
    items = ExpenseItemSerializer(many=True, read_only=True)

    class Meta:
        model = ExpenseReport
        fields = "__all__"
        read_only_fields = ("id", "tenant")


# -------- Payment orders
class PaymentOrderLineSerializer(TenantReadOnlyMixin):
    bill_number = serializers.CharField(source="bill.number", read_only=True)

    class Meta:
        model = PaymentOrderLine
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class PaymentOrderSerializer(TenantReadOnlyMixin):
    lines = PaymentOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentOrder
        fields = "__all__"
        read_only_fields = ("id", "tenant")


# -------- Treasury
class BankConnectorSerializer(TenantReadOnlyMixin):
    class Meta:
        model = BankConnector
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class BankAccountSerializer(TenantReadOnlyMixin):
    connector_name = serializers.CharField(source="connector.name", read_only=True)

    class Meta:
        model = BankAccount
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class BankTransactionSerializer(TenantReadOnlyMixin):
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True)

    class Meta:
        model = BankTransaction
        fields = "__all__"
        read_only_fields = ("id", "tenant")


class ReconciliationMatchSerializer(TenantReadOnlyMixin):
    class Meta:
        model = ReconciliationMatch
        fields = "__all__"
        read_only_fields = ("id", "tenant", "matched_at")


# -------- Reporting
class ReportSnapshotSerializer(TenantReadOnlyMixin):
    class Meta:
        model = ReportSnapshot
        fields = "__all__"
        read_only_fields = ("id", "tenant", "generated_at")