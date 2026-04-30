# finance/urls.py
from django.urls import path, include

from . import views
from .views import invoice_pdf

app_name = "finance"



def crud_urls(V):
    ListV, DetailV, CreateV, UpdateV, DeleteV = V
    return [
        path("", ListV.as_view(), name="list"),
        path("new/", CreateV.as_view(), name="create"),
        path("<uuid:pk>/", DetailV.as_view(), name="detail"),
        path("<uuid:pk>/edit/", UpdateV.as_view(), name="update"),
        path("<uuid:pk>/delete/", DeleteV.as_view(), name="delete"),
    ]


def crud_include(namespace: str, V):
    """
    Déclare un sous-namespace:
      finance:<namespace>:list
    """
    return path(f"{namespace.replace('_','-')}/", include((crud_urls(V), namespace), namespace=namespace))


def custom_include(prefix: str, namespace: str, patterns):
    """
    Pour les CRUD custom (avec lignes): quotes/invoices/journal_entries/...
    """
    return path(prefix, include((patterns, namespace), namespace=namespace))


urlpatterns = [
    # --- Audit ---
    path("api/", include("finance.api.routers")),
    path("quotes/<uuid:pk>/pdf/", views.QuotePDFView.as_view(), name="quote_pdf"),

    crud_include("audit_events", views.AuditEventViews),

    # --- Core accounting ---
    crud_include("profiles", views.CompanyFinanceProfileViews),
    crud_include("fiscal_years", views.FiscalYearViews),
    crud_include("periods", views.AccountingPeriodViews),
    crud_include("accounts", views.AccountViews),
    crud_include("journals", views.JournalViews),
    crud_include("taxes", views.TaxViews),
    crud_include("closings", views.FiscalClosingViews),

    # --- FX ---
    crud_include("fx", views.ExchangeRateViews),

    # --- Partners ---
    crud_include("partners", views.PartnerViews),

    # --- Payments ---
    crud_include("payments", views.PaymentViews),

    # --- Subscriptions / dunning / portal ---
    crud_include("subscription_plans", views.SubscriptionPlanViews),
    crud_include("subscriptions", views.SubscriptionViews),
    crud_include("dunning_stages", views.DunningStageViews),
    crud_include("dunning_events", views.DunningEventViews),
    crud_include("portal_tokens", views.CustomerPortalTokenViews),

    # --- Treasury ---
    crud_include("bank_connectors", views.BankConnectorViews),
    crud_include("bank_accounts", views.BankAccountViews),
    crud_include("bank_transactions", views.BankTransactionViews),
    crud_include("reconciliations", views.ReconciliationMatchViews),

    # --- Reporting ---
    crud_include("reports", views.ReportSnapshotViews),

    # ==========================
    # CRUD custom (patterns dédiés)
    # ==========================

    # --- Journal entries (custom create/update with lines) ---
    custom_include("journal-entries/", "journal_entries", [
        path("", views.JournalEntryList.as_view(), name="list"),
        path("new/", views.JournalEntryCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.JournalEntryDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.JournalEntryUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.JournalEntryDelete.as_view(), name="delete"),
    ]),

    # --- Quotes (custom create/update with lines) ---
    custom_include("quotes/", "quotes", [
        path("", views.QuoteList.as_view(), name="list"),
        path("new/", views.QuoteCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.QuoteDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.QuoteUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.QuoteDelete.as_view(), name="delete"),
    ]),

    # --- Invoices (custom create/update with lines) ---
    custom_include("invoices/", "invoices", [
        path("", views.InvoiceList.as_view(), name="list"),
        path("new/", views.InvoiceCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.InvoiceDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.InvoiceUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.InvoiceDelete.as_view(), name="delete"),
        path("<uuid:pk>/pdf/", invoice_pdf, name="pdf"),

    ]),

    # --- Vendor bills (custom create/update with lines) ---
    custom_include("vendor-bills/", "vendor_bills", [
        path("", views.VendorBillList.as_view(), name="list"),
        path("new/", views.VendorBillCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.VendorBillDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.VendorBillUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.VendorBillDelete.as_view(), name="delete"),
    ]),

    # --- Expense reports (custom create/update with lines) ---
    custom_include("expense-reports/", "expense_reports", [
        path("", views.ExpenseReportList.as_view(), name="list"),
        path("new/", views.ExpenseReportCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.ExpenseReportDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.ExpenseReportUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.ExpenseReportDelete.as_view(), name="delete"),
    ]),

    # --- Payment orders (custom create/update with lines) ---
    custom_include("payment-orders/", "payment_orders", [
        path("", views.PaymentOrderList.as_view(), name="list"),
        path("new/", views.PaymentOrderCreate.as_view(), name="create"),
        path("<uuid:pk>/", views.PaymentOrderDetail.as_view(), name="detail"),
        path("<uuid:pk>/edit/", views.PaymentOrderUpdate.as_view(), name="update"),
        path("<uuid:pk>/delete/", views.PaymentOrderDelete.as_view(), name="delete"),
    ]),
]
