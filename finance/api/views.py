# finance/api/views.py
import uuid

from rest_framework import viewsets, filters
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet

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
from .serializers import (
    AuditEventSerializer,
    CompanyFinanceProfileSerializer, FiscalYearSerializer, AccountingPeriodSerializer,
    AccountSerializer, JournalSerializer, JournalEntrySerializer, JournalLineSerializer, TaxSerializer,
    FiscalClosingSerializer,
    ExchangeRateSerializer, PartnerSerializer,
    QuoteSerializer, QuoteLineSerializer, InvoiceSerializer, InvoiceLineSerializer, PaymentSerializer,
    SubscriptionPlanSerializer, SubscriptionSerializer, DunningStageSerializer, DunningEventSerializer,
    CustomerPortalTokenSerializer,
    VendorBillSerializer, VendorBillLineSerializer, ExpenseReportSerializer, ExpenseItemSerializer,
    PaymentOrderSerializer, PaymentOrderLineSerializer,
    BankConnectorSerializer, BankAccountSerializer, BankTransactionSerializer, ReconciliationMatchSerializer,
    ReportSnapshotSerializer,
)


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False


def _get_tenant_value_from_request(request):
    """
    Retourne ce que tu as (UUID ou slug), sans présumer.
    Ordre: request.tenant > header > querystring > sous-domaine (si tu le fais déjà)
    """
    # 1) middleware
    tenant = getattr(request, "tenant", None)
    if tenant:
        return str(getattr(tenant, "id", ""))  # déjà un UUID

    # 2) headers
    v = (
            request.headers.get("X-Tenant-Id")
            or request.headers.get("X-Tenant-Slug")
            or request.headers.get("X-Tenant")
    )
    if v:
        return v.strip()

    # 3) query param
    v = request.query_params.get("tenant")
    if v:
        return v.strip()

    # 4) fallback: sous-domaine (ex: rh.lyneerp.com => "rh")
    host = (request.get_host() or "").split(":")[0]
    parts = host.split(".")
    if len(parts) >= 3:
        return parts[0].strip()

    return None


# ---------- Tenant resolver (API)
def _get_tenant_id_from_request(request):
    """
    Retourne TOUJOURS un UUID (string) ou None.
    Accepte UUID direct OU slug, et résout en Tenant.id.
    """
    v = _get_tenant_value_from_request(request)
    if not v:
        return None

    # UUID direct
    if _is_uuid(v):
        return str(uuid.UUID(v))

    # Sinon => slug
    try:
        return str(Tenant.objects.only("id").get(slug=v).id)
    except Tenant.DoesNotExist:
        return None


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


class TenantScopedViewSet(viewsets.ModelViewSet):
    """
    - filtre automatiquement sur tenant
    - force tenant à la création
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    tenant_field = "tenant"

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = _get_tenant_id_from_request(self.request)
        if not tenant_id:
            return qs.none()
        return qs.filter(**{f"{self.tenant_field}_id": tenant_id})

    def perform_create(self, serializer):
        tenant_id = _get_tenant_id_from_request(self.request)
        if not tenant_id:
            raise ValidationError("Tenant introuvable pour la création.")
        serializer.save(**{f"{self.tenant_field}_id": tenant_id})


# ---------- ViewSets
class AuditEventViewSet(TenantScopedViewSet):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    search_fields = ("model_label", "object_id", "object_repr", "action")
    ordering_fields = ("created_at",)


class CompanyFinanceProfileViewSet(TenantScopedViewSet):
    queryset = CompanyFinanceProfile.objects.all()
    serializer_class = CompanyFinanceProfileSerializer
    search_fields = ("standard", "base_currency")
    ordering_fields = ("id",)


class FiscalYearViewSet(TenantScopedViewSet):
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    search_fields = ("name",)
    ordering_fields = ("date_start", "date_end", "name")


class AccountingPeriodViewSet(TenantScopedViewSet):
    queryset = AccountingPeriod.objects.select_related("fiscal_year").all()
    serializer_class = AccountingPeriodSerializer
    search_fields = ("name", "status")
    ordering_fields = ("date_start", "date_end", "name")


class AccountViewSet(TenantScopedViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    search_fields = ("code", "name", "type")
    ordering_fields = ("code", "name", "type")


class JournalViewSet(TenantScopedViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    search_fields = ("code", "name", "type")
    ordering_fields = ("code", "name", "type")


class JournalEntryViewSet(TenantScopedViewSet):
    queryset = JournalEntry.objects.select_related("journal", "period").all()
    serializer_class = JournalEntrySerializer
    search_fields = ("reference", "label", "status", "source_model", "source_object_id")
    ordering_fields = ("entry_date", "created_at")


class JournalLineViewSet(TenantScopedViewSet):
    queryset = JournalLine.objects.select_related("entry", "account").all()
    serializer_class = JournalLineSerializer
    search_fields = ("label", "partner_label", "currency")
    ordering_fields = ("debit", "credit")


class TaxViewSet(TenantScopedViewSet):
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    search_fields = ("name", "scope")
    ordering_fields = ("rate", "name")


class FiscalClosingViewSet(TenantScopedViewSet):
    queryset = FiscalClosing.objects.select_related("fiscal_year").all()
    serializer_class = FiscalClosingSerializer
    search_fields = ("status", "notes")
    ordering_fields = ("generated_at", "posted_at")


class ExchangeRateViewSet(TenantScopedViewSet):
    queryset = ExchangeRate.objects.all()
    serializer_class = ExchangeRateSerializer
    search_fields = ("base_currency", "quote_currency", "source")
    ordering_fields = ("date", "rate")


class PartnerViewSet(TenantScopedViewSet):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    search_fields = ("code", "name", "email", "phone", "vat_number", "type")
    ordering_fields = ("code", "name", "type")


class TenantFilteredViewSet(ModelViewSet):
    tenant_field = "tenant"  # FK name

    def get_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            raise NotFound("Tenant non résolu (middleware).")
        return tenant

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = self.get_tenant()
        return qs.filter(**{self.tenant_field: tenant})


class QuoteViewSet(TenantScopedViewSet):
    queryset = Quote.objects.select_related("partner").prefetch_related("lines").all()
    serializer_class = QuoteSerializer
    search_fields = ("number", "status", "partner__name")
    ordering_fields = ("issue_date", "created_at", "number")


class QuoteLineViewSet(TenantScopedViewSet):
    queryset = QuoteLine.objects.select_related("quote", "tax").all()
    serializer_class = QuoteLineSerializer
    search_fields = ("label", "quote__number")
    ordering_fields = ("quantity", "unit_price")


class InvoiceViewSet(TenantScopedViewSet):
    queryset = Invoice.objects.select_related("partner", "quote").prefetch_related("lines").all()
    serializer_class = InvoiceSerializer
    search_fields = ("number", "status", "partner__name")
    ordering_fields = ("issue_date", "due_date", "created_at", "number")


class InvoiceLineViewSet(TenantScopedViewSet):
    queryset = InvoiceLine.objects.select_related("invoice", "tax").all()
    serializer_class = InvoiceLineSerializer
    search_fields = ("label", "invoice__number")
    ordering_fields = ("quantity", "unit_price")


class PaymentViewSet(TenantScopedViewSet):
    queryset = Payment.objects.select_related("invoice", "invoice__partner").all()
    serializer_class = PaymentSerializer
    search_fields = ("reference", "provider", "invoice__number", "invoice__partner__name")
    ordering_fields = ("paid_at", "amount", "created_at")


class SubscriptionPlanViewSet(TenantScopedViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    search_fields = ("name", "description")
    ordering_fields = ("amount", "name")


class SubscriptionViewSet(TenantScopedViewSet):
    queryset = Subscription.objects.select_related("partner", "plan").all()
    serializer_class = SubscriptionSerializer
    search_fields = ("partner__name", "plan__name", "status")
    ordering_fields = ("start_date", "end_date", "next_invoice_date")


class DunningStageViewSet(TenantScopedViewSet):
    queryset = DunningStage.objects.all()
    serializer_class = DunningStageSerializer
    search_fields = ("name", "email_subject")
    ordering_fields = ("days_after_due", "name")


class DunningEventViewSet(TenantScopedViewSet):
    queryset = DunningEvent.objects.select_related("invoice", "stage").all()
    serializer_class = DunningEventSerializer
    search_fields = ("invoice__number", "stage__name", "channel")
    ordering_fields = ("sent_at",)


class CustomerPortalTokenViewSet(TenantScopedViewSet):
    queryset = CustomerPortalToken.objects.select_related("partner").all()
    serializer_class = CustomerPortalTokenSerializer
    search_fields = ("partner__name", "token")
    ordering_fields = ("expires_at", "created_at")


class VendorBillViewSet(TenantScopedViewSet):
    queryset = VendorBill.objects.select_related("supplier").prefetch_related("lines").all()
    serializer_class = VendorBillSerializer
    search_fields = ("number", "status", "supplier__name")
    ordering_fields = ("bill_date", "due_date", "created_at")


class VendorBillLineViewSet(TenantScopedViewSet):
    queryset = VendorBillLine.objects.select_related("bill", "tax").all()
    serializer_class = VendorBillLineSerializer
    search_fields = ("label", "bill__number", "expense_account_code")
    ordering_fields = ("quantity", "unit_price")


class ExpenseReportViewSet(TenantScopedViewSet):
    queryset = ExpenseReport.objects.prefetch_related("items").all()
    serializer_class = ExpenseReportSerializer
    search_fields = ("title", "employee_id", "status")
    ordering_fields = ("submitted_at", "created_at")


class ExpenseItemViewSet(TenantScopedViewSet):
    queryset = ExpenseItem.objects.select_related("report", "tax").all()
    serializer_class = ExpenseItemSerializer
    search_fields = ("label", "category", "report__title")
    ordering_fields = ("date", "amount")


class PaymentOrderViewSet(TenantScopedViewSet):
    queryset = PaymentOrder.objects.prefetch_related("lines").all()
    serializer_class = PaymentOrderSerializer
    search_fields = ("name", "status")
    ordering_fields = ("created_at", "total_amount")


class PaymentOrderLineViewSet(TenantScopedViewSet):
    queryset = PaymentOrderLine.objects.select_related("order", "bill").all()
    serializer_class = PaymentOrderLineSerializer
    search_fields = ("beneficiary_name", "reference", "bill__number", "order__name")
    ordering_fields = ("amount",)


class BankConnectorViewSet(TenantScopedViewSet):
    queryset = BankConnector.objects.all()
    serializer_class = BankConnectorSerializer
    search_fields = ("name", "provider")
    ordering_fields = ("name", "provider")


class BankAccountViewSet(TenantScopedViewSet):
    queryset = BankAccount.objects.select_related("connector").all()
    serializer_class = BankAccountSerializer
    search_fields = ("name", "iban", "external_id")
    ordering_fields = ("name", "currency")


class BankTransactionViewSet(TenantScopedViewSet):
    queryset = BankTransaction.objects.select_related("bank_account").all()
    serializer_class = BankTransactionSerializer
    search_fields = ("label", "external_id")
    ordering_fields = ("date", "amount")


class ReconciliationMatchViewSet(TenantScopedViewSet):
    queryset = ReconciliationMatch.objects.select_related("bank_transaction").all()
    serializer_class = ReconciliationMatchSerializer
    search_fields = ("match_type", "target_model", "target_object_id")
    ordering_fields = ("matched_at",)


class ReportSnapshotViewSet(TenantScopedViewSet):
    queryset = ReportSnapshot.objects.all()
    serializer_class = ReportSnapshotSerializer
    search_fields = ("report_type",)
    ordering_fields = ("generated_at",)
