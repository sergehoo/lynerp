# finance/api/routers.py
from rest_framework.routers import DefaultRouter
from .views import (
    AuditEventViewSet,
    CompanyFinanceProfileViewSet,
    FiscalYearViewSet,
    AccountingPeriodViewSet,
    AccountViewSet,
    JournalViewSet,
    JournalEntryViewSet,
    JournalLineViewSet,
    TaxViewSet,
    FiscalClosingViewSet,
    ExchangeRateViewSet,
    PartnerViewSet,
    QuoteViewSet,
    QuoteLineViewSet,
    InvoiceViewSet,
    InvoiceLineViewSet,
    PaymentViewSet,
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
    DunningStageViewSet,
    DunningEventViewSet,
    CustomerPortalTokenViewSet,
    VendorBillViewSet,
    VendorBillLineViewSet,
    ExpenseReportViewSet,
    ExpenseItemViewSet,
    PaymentOrderViewSet,
    PaymentOrderLineViewSet,
    BankConnectorViewSet,
    BankAccountViewSet,
    BankTransactionViewSet,
    ReconciliationMatchViewSet,
    ReportSnapshotViewSet,
)

router = DefaultRouter(trailing_slash=True)

# --- Audit
router.register(r"audit-events", AuditEventViewSet, basename="finance-audit-events")

# --- Core accounting
router.register(r"profiles", CompanyFinanceProfileViewSet, basename="finance-profiles")
router.register(r"fiscal-years", FiscalYearViewSet, basename="finance-fiscal-years")
router.register(r"periods", AccountingPeriodViewSet, basename="finance-periods")
router.register(r"accounts", AccountViewSet, basename="finance-accounts")
router.register(r"journals", JournalViewSet, basename="finance-journals")
router.register(r"journal-entries", JournalEntryViewSet, basename="finance-journal-entries")
router.register(r"journal-lines", JournalLineViewSet, basename="finance-journal-lines")
router.register(r"taxes", TaxViewSet, basename="finance-taxes")
router.register(r"closings", FiscalClosingViewSet, basename="finance-closings")

# --- FX / Partners / Sales
router.register(r"fx", ExchangeRateViewSet, basename="finance-fx")
router.register(r"partners", PartnerViewSet, basename="finance-partners")
router.register(r"quotes", QuoteViewSet, basename="finance-quotes")
router.register(r"quote-lines", QuoteLineViewSet, basename="finance-quote-lines")
router.register(r"invoices", InvoiceViewSet, basename="finance-invoices")
router.register(r"invoice-lines", InvoiceLineViewSet, basename="finance-invoice-lines")
router.register(r"payments", PaymentViewSet, basename="finance-payments")

# --- Subscriptions / dunning / portal
router.register(r"subscription-plans", SubscriptionPlanViewSet, basename="finance-subscription-plans")
router.register(r"subscriptions", SubscriptionViewSet, basename="finance-subscriptions")
router.register(r"dunning-stages", DunningStageViewSet, basename="finance-dunning-stages")
router.register(r"dunning-events", DunningEventViewSet, basename="finance-dunning-events")
router.register(r"portal-tokens", CustomerPortalTokenViewSet, basename="finance-portal-tokens")

# --- Purchases
router.register(r"vendor-bills", VendorBillViewSet, basename="finance-vendor-bills")
router.register(r"vendor-bill-lines", VendorBillLineViewSet, basename="finance-vendor-bill-lines")
router.register(r"expense-reports", ExpenseReportViewSet, basename="finance-expense-reports")
router.register(r"expense-items", ExpenseItemViewSet, basename="finance-expense-items")

# --- Payment orders
router.register(r"payment-orders", PaymentOrderViewSet, basename="finance-payment-orders")
router.register(r"payment-order-lines", PaymentOrderLineViewSet, basename="finance-payment-order-lines")

# --- Treasury
router.register(r"bank-connectors", BankConnectorViewSet, basename="finance-bank-connectors")
router.register(r"bank-accounts", BankAccountViewSet, basename="finance-bank-accounts")
router.register(r"bank-transactions", BankTransactionViewSet, basename="finance-bank-transactions")
router.register(r"reconciliations", ReconciliationMatchViewSet, basename="finance-reconciliations")

# --- Reporting
router.register(r"reports", ReportSnapshotViewSet, basename="finance-reports")

urlpatterns = router.urls