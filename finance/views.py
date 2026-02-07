# finance/views.py
from __future__ import annotations
from typing import Any, Type, Tuple
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

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
from .forms import (
    TenantModelForm,
    CompanyFinanceProfileForm, FiscalYearForm, AccountingPeriodForm, AccountForm, JournalForm,
    JournalEntryForm, JournalLineFormSet,
    TaxForm, FiscalClosingForm,
    ExchangeRateForm, PartnerForm,
    QuoteForm, QuoteLineFormSet,
    InvoiceForm, InvoiceLineFormSet,
    PaymentForm,
    SubscriptionPlanForm, SubscriptionForm,
    DunningStageForm, DunningEventForm, CustomerPortalTokenForm,
    VendorBillForm, VendorBillLineFormSet,
    ExpenseReportForm, ExpenseItemFormSet,
    PaymentOrderForm, PaymentOrderLineFormSet,
    BankConnectorForm, BankAccountForm, BankTransactionForm,
    ReconciliationMatchForm,
    ReportSnapshotForm,
)


# ========= Tenant resolver =========
def get_current_tenant(request: HttpRequest):
    """
    À adapter à ton middleware / tenant resolver.
    Idéal: request.tenant déjà défini.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise RuntimeError("Tenant non résolu. Assure-toi d'avoir un middleware qui met request.tenant.")
    return tenant


class TenantQuerysetMixin:
    """
    Applique automatiquement le scope tenant au queryset.

    Par défaut filtre sur le champ FK 'tenant'.
    Surchargable via tenant_field.
    """
    tenant_field = "tenant"

    def get_tenant(self):
        # Source unique : middleware -> request.tenant
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return tenant

        # fallback : request.tenant_id si dispo
        tenant_id = getattr(self.request, "tenant_id", None)
        if tenant_id:
            # Evite une requête si tu filtres par ID (voir get_queryset)
            return None

        return None

    def get_queryset(self):
        qs = super().get_queryset()

        tenant = getattr(self.request, "tenant", None)
        if tenant:
            return qs.filter(**{self.tenant_field: tenant})

        tenant_id = getattr(self.request, "tenant_id", None)
        if tenant_id:
            # FK: tenant_id (UUID) => filtre direct sans fetch Tenant
            return qs.filter(**{f"{self.tenant_field}_id": tenant_id})

        # Sécurité: si aucun tenant, retourne vide (ou raise)
        return qs.none()

class JsonListMixin:
    json_fields = ()

    def render_to_response(self, context, **response_kwargs):
        want_json = (
            self.request.headers.get("Accept", "").find("application/json") >= 0
            or self.request.GET.get("format") == "json"
        )
        if not want_json:
            return super().render_to_response(context, **response_kwargs)

        qs = context["object_list"]
        page = int(self.request.GET.get("page", 1))
        page_size = int(self.request.GET.get("page_size", 20))

        paginator = Paginator(qs, page_size)
        p = paginator.get_page(page)

        def serialize(o):
            data = {"id": str(o.pk)}
            for f in self.json_fields:
                val = getattr(o, f, None)
                data[f] = str(val) if val is not None else None
            return data

        return JsonResponse({
            "results": [serialize(o) for o in p.object_list],
            "next": p.has_next(),
            "count": paginator.count,
        })
class TenantFormMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = get_current_tenant(self.request)
        return kwargs

    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, "tenant_id") and not obj.tenant_id:
            obj.tenant = get_current_tenant(self.request)
        return super().form_valid(form)


class SearchableListMixin:
    search_param = "q"
    search_fields: tuple[str, ...] = ()

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.GET.get(self.search_param) or "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        return qs


class BaseTenantList(LoginRequiredMixin, PermissionRequiredMixin, TenantQuerysetMixin, SearchableListMixin, ListView):
    paginate_by = 30


class BaseTenantDetail(LoginRequiredMixin, PermissionRequiredMixin, TenantQuerysetMixin, DetailView):
    pass


class BaseTenantCreate(LoginRequiredMixin, PermissionRequiredMixin, TenantFormMixin, CreateView):
    pass


class BaseTenantUpdate(LoginRequiredMixin, PermissionRequiredMixin, TenantQuerysetMixin, TenantFormMixin, UpdateView):
    pass


class BaseTenantDelete(LoginRequiredMixin, PermissionRequiredMixin, TenantQuerysetMixin, DeleteView):
    pass


# ========= MASTER + LINES generic =========
class MasterWithLinesMixin(TenantQuerysetMixin, TenantFormMixin):
    """
    Combine un ModelForm + un inline formset.
    """
    formset_class = None  # type: ignore
    formset_prefix = "lines"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "formset" not in ctx:
            ctx["formset"] = self.get_formset()
        return ctx

    def get_formset(self):
        assert self.formset_class is not None, "formset_class is required"
        if self.request.method == "POST":
            return self.formset_class(self.request.POST, self.request.FILES, instance=self.object, prefix=self.formset_prefix)
        return self.formset_class(instance=self.object, prefix=self.formset_prefix)

    @transaction.atomic
    def form_valid(self, form):
        tenant = get_current_tenant(self.request)
        self.object = form.save(commit=False)
        if hasattr(self.object, "tenant_id") and not self.object.tenant_id:
            self.object.tenant = tenant
        self.object.save()

        formset = self.get_formset()
        if not formset.is_valid():
            return self.form_invalid(form)

        # force tenant sur les lignes
        lines = formset.save(commit=False)
        for line in lines:
            if hasattr(line, "tenant_id") and not line.tenant_id:
                line.tenant = tenant
            line.save()
        formset.save_m2m()
        for deleted in formset.deleted_objects:
            deleted.delete()

        messages.success(self.request, "Enregistré avec succès.")
        return redirect(self.get_success_url())


# ========= Simple CRUD generator (no repetition) =========
def crud_views(
    *,
    model: Type,  # ou Type[models.Model] si tu veux être strict
    form_class: Type[TenantModelForm],
    base_url: str,          # ex: "finance:accounts" ou "finance:invoices" (namespace géré ailleurs)
    template_dir: str,      # ex: "accounts"
    list_search_fields: tuple[str, ...] = (),
    ordering: tuple[str, ...] = ("-created_at",),
):
    """
    Génère List/Detail/Create/Update/Delete pour un modèle.
    Templates:
      finance/<template_dir>/list.html
      finance/<template_dir>/detail.html
      finance/<template_dir>/form.html
      finance/<template_dir>/confirm_delete.html
    """

    # ✅ Fix: renommer pour éviter l'auto-référence "model = model"
    model_cls = model
    form_cls = form_class
    default_ordering: Tuple[str, ...] = ordering
    search_fields: Tuple[str, ...] = list_search_fields

    app_label = model_cls._meta.app_label
    model_name = model_cls._meta.model_name

    # ✅ Tip: success_url basé sur "base_url" (ex: "finance:accounts") + ":list"
    list_url_name = f"{base_url}:list"

    class _List(JsonListMixin, BaseTenantList):
        model = model_cls
        permission_required = f"{app_label}.view_{model_name}"
        template_name = f"finance/{template_dir}/list.html"
        # search_fields = search_fields
        ordering = default_ordering
        json_fields = getattr(model_cls, "JSON_FIELDS", ())

    class _Detail(BaseTenantDetail):
        model = model_cls
        permission_required = f"{app_label}.view_{model_name}"
        template_name = f"finance/{template_dir}/detail.html"

    class _Create(BaseTenantCreate):
        model = model_cls
        form_class = form_cls
        permission_required = f"{app_label}.add_{model_name}"
        template_name = f"finance/{template_dir}/form.html"
        success_url = reverse_lazy(list_url_name)

    class _Update(BaseTenantUpdate):
        model = model_cls
        form_class = form_cls
        permission_required = f"{app_label}.change_{model_name}"
        template_name = f"finance/{template_dir}/form.html"
        success_url = reverse_lazy(list_url_name)

    class _Delete(BaseTenantDelete):
        model = model_cls
        permission_required = f"{app_label}.delete_{model_name}"
        template_name = f"finance/{template_dir}/confirm_delete.html"
        success_url = reverse_lazy(list_url_name)

    return _List, _Detail, _Create, _Update, _Delete


# ========= Master + lines views =========
class JournalEntryCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = JournalEntry
    form_class = JournalEntryForm
    permission_required = "finance.add_journalentry"
    template_name = "finance/journal_entry/form_with_lines.html"
    success_url = reverse_lazy("finance:journal_entries:list")
    formset_class = JournalLineFormSet

    def get(self, request, *args, **kwargs):
        self.object = None
        self.object = JournalEntry(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class JournalEntryUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = JournalEntry
    form_class = JournalEntryForm
    permission_required = "finance.change_journalentry"
    template_name = "finance/journal_entry/form_with_lines.html"
    success_url = reverse_lazy("finance:journal_entries:list")
    formset_class = JournalLineFormSet


class QuoteCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = Quote
    form_class = QuoteForm
    permission_required = "finance.add_quote"
    template_name = "finance/quote/form_with_lines.html"
    success_url = reverse_lazy("finance:quotes:list")
    formset_class = QuoteLineFormSet

    def get(self, request, *args, **kwargs):
        self.object = Quote(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class QuoteUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = Quote
    form_class = QuoteForm
    permission_required = "finance.change_quote"
    template_name = "finance/quote/form_with_lines.html"
    success_url = reverse_lazy("finance:quotes:list")
    formset_class = QuoteLineFormSet


class InvoiceCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    permission_required = "finance.add_invoice"
    template_name = "finance/invoice/form_with_lines.html"
    success_url = reverse_lazy("finance:invoices:list")
    formset_class = InvoiceLineFormSet

    def get(self, request, *args, **kwargs):
        self.object = Invoice(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class InvoiceUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    permission_required = "finance.change_invoice"
    template_name = "finance/invoice/form_with_lines.html"
    success_url = reverse_lazy("finance:invoices:list")
    formset_class = InvoiceLineFormSet


class VendorBillCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = VendorBill
    form_class = VendorBillForm
    permission_required = "finance.add_vendorbill"
    template_name = "finance/vendor_bill/form_with_lines.html"
    success_url = reverse_lazy("finance:vendor_bills:list")
    formset_class = VendorBillLineFormSet

    def get(self, request, *args, **kwargs):
        self.object = VendorBill(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class VendorBillUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = VendorBill
    form_class = VendorBillForm
    permission_required = "finance.change_vendorbill"
    template_name = "finance/vendor_bill/form_with_lines.html"
    success_url = reverse_lazy("finance:vendor_bills:list")
    formset_class = VendorBillLineFormSet


class ExpenseReportCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = ExpenseReport
    form_class = ExpenseReportForm
    permission_required = "finance.add_expensereport"
    template_name = "finance/expense_report/form_with_lines.html"
    success_url = reverse_lazy("finance:expense_reports:list")
    formset_class = ExpenseItemFormSet

    def get(self, request, *args, **kwargs):
        self.object = ExpenseReport(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class ExpenseReportUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = ExpenseReport
    form_class = ExpenseReportForm
    permission_required = "finance.change_expensereport"
    template_name = "finance/expense_report/form_with_lines.html"
    success_url = reverse_lazy("finance:expense_reports:list")
    formset_class = ExpenseItemFormSet


class PaymentOrderCreate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, CreateView):
    model = PaymentOrder
    form_class = PaymentOrderForm
    permission_required = "finance.add_paymentorder"
    template_name = "finance/payment_order/form_with_lines.html"
    success_url = reverse_lazy("finance:payment_orders:list")
    formset_class = PaymentOrderLineFormSet

    def get(self, request, *args, **kwargs):
        self.object = PaymentOrder(tenant=get_current_tenant(request))
        return super().get(request, *args, **kwargs)


class PaymentOrderUpdate(LoginRequiredMixin, PermissionRequiredMixin, MasterWithLinesMixin, UpdateView):
    model = PaymentOrder
    form_class = PaymentOrderForm
    permission_required = "finance.change_paymentorder"
    template_name = "finance/payment_order/form_with_lines.html"
    success_url = reverse_lazy("finance:payment_orders:list")
    formset_class = PaymentOrderLineFormSet


# ========= CRUD for all other models =========
AuditEventViews = crud_views(
    model=AuditEvent,
    form_class=TenantModelForm,  # read-only in practice; tu peux créer un form dédié si tu veux
    base_url="finance:audit_events",
    template_dir="audit_event",
    list_search_fields=("model_label", "object_id", "object_repr"),
    ordering=("-created_at",),
)

CompanyFinanceProfileViews = crud_views(model=CompanyFinanceProfile, form_class=CompanyFinanceProfileForm, base_url="finance:profiles", template_dir="profile")
FiscalYearViews = crud_views(model=FiscalYear, form_class=FiscalYearForm, base_url="finance:fiscal_years", template_dir="fiscal_year", list_search_fields=("name",))
AccountingPeriodViews = crud_views(model=AccountingPeriod, form_class=AccountingPeriodForm, base_url="finance:periods", template_dir="period", list_search_fields=("name",))
AccountViews = crud_views(model=Account, form_class=AccountForm, base_url="finance:accounts", template_dir="account", list_search_fields=("code", "name"))
JournalViews = crud_views(model=Journal, form_class=JournalForm, base_url="finance:journals", template_dir="journal", list_search_fields=("code", "name"))

# JournalEntry uses custom master+lines create/update; list/detail/delete still generic:
JournalEntryList, JournalEntryDetail, _, _, JournalEntryDelete = crud_views(
    model=JournalEntry, form_class=JournalEntryForm, base_url="finance:journal_entries", template_dir="journal_entry",
    list_search_fields=("reference", "label", "source_object_id"),
    ordering=("-entry_date", "-created_at"),
)
JournalLineViews = crud_views(model=JournalLine, form_class=TenantModelForm, base_url="finance:journal_lines", template_dir="journal_line")

TaxViews = crud_views(model=Tax, form_class=TaxForm, base_url="finance:taxes", template_dir="tax", list_search_fields=("name",))
FiscalClosingViews = crud_views(model=FiscalClosing, form_class=FiscalClosingForm, base_url="finance:closings", template_dir="closing")

ExchangeRateViews = crud_views(model=ExchangeRate, form_class=ExchangeRateForm, base_url="finance:fx", template_dir="exchange_rate")
PartnerViews = crud_views(model=Partner, form_class=PartnerForm, base_url="finance:partners", template_dir="partner", list_search_fields=("code", "name", "email"))

# Quote/Invoice use custom master+lines create/update; list/detail/delete generic:
QuoteList, QuoteDetail, _, _, QuoteDelete = crud_views(model=Quote, form_class=QuoteForm, base_url="finance:quotes", template_dir="quote", list_search_fields=("number",))
QuoteLineViews = crud_views(model=QuoteLine, form_class=TenantModelForm, base_url="finance:quote_lines", template_dir="quote_line")
InvoiceList, InvoiceDetail, _, _, InvoiceDelete = crud_views(model=Invoice, form_class=InvoiceForm, base_url="finance:invoices", template_dir="invoice", list_search_fields=("number",))
InvoiceLineViews = crud_views(model=InvoiceLine, form_class=TenantModelForm, base_url="finance:invoice_lines", template_dir="invoice_line")

PaymentViews = crud_views(model=Payment, form_class=PaymentForm, base_url="finance:payments", template_dir="payment", list_search_fields=("reference", "provider"))

SubscriptionPlanViews = crud_views(model=SubscriptionPlan, form_class=SubscriptionPlanForm, base_url="finance:subscription_plans", template_dir="subscription_plan", list_search_fields=("name",))
SubscriptionViews = crud_views(model=Subscription, form_class=SubscriptionForm, base_url="finance:subscriptions", template_dir="subscription")

DunningStageViews = crud_views(model=DunningStage, form_class=DunningStageForm, base_url="finance:dunning_stages", template_dir="dunning_stage", list_search_fields=("name",))
DunningEventViews = crud_views(model=DunningEvent, form_class=DunningEventForm, base_url="finance:dunning_events", template_dir="dunning_event")
CustomerPortalTokenViews = crud_views(model=CustomerPortalToken, form_class=CustomerPortalTokenForm, base_url="finance:portal_tokens", template_dir="portal_token")

# VendorBill/ExpenseReport/PaymentOrder use custom master+lines create/update; list/detail/delete generic:
VendorBillList, VendorBillDetail, _, _, VendorBillDelete = crud_views(model=VendorBill, form_class=VendorBillForm, base_url="finance:vendor_bills", template_dir="vendor_bill", list_search_fields=("number",))
VendorBillLineViews = crud_views(model=VendorBillLine, form_class=TenantModelForm, base_url="finance:vendor_bill_lines", template_dir="vendor_bill_line")

ExpenseReportList, ExpenseReportDetail, _, _, ExpenseReportDelete = crud_views(model=ExpenseReport, form_class=ExpenseReportForm, base_url="finance:expense_reports", template_dir="expense_report", list_search_fields=("title", "employee_id"))
ExpenseItemViews = crud_views(model=ExpenseItem, form_class=TenantModelForm, base_url="finance:expense_items", template_dir="expense_item")

PaymentOrderList, PaymentOrderDetail, _, _, PaymentOrderDelete = crud_views(model=PaymentOrder, form_class=PaymentOrderForm, base_url="finance:payment_orders", template_dir="payment_order", list_search_fields=("name",))
PaymentOrderLineViews = crud_views(model=PaymentOrderLine, form_class=TenantModelForm, base_url="finance:payment_order_lines", template_dir="payment_order_line")

BankConnectorViews = crud_views(model=BankConnector, form_class=BankConnectorForm, base_url="finance:bank_connectors", template_dir="bank_connector", list_search_fields=("name",))
BankAccountViews = crud_views(model=BankAccount, form_class=BankAccountForm, base_url="finance:bank_accounts", template_dir="bank_account", list_search_fields=("name", "iban", "external_id"))
BankTransactionViews = crud_views(model=BankTransaction, form_class=BankTransactionForm, base_url="finance:bank_transactions", template_dir="bank_transaction", list_search_fields=("label", "external_id"))
ReconciliationMatchViews = crud_views(model=ReconciliationMatch, form_class=ReconciliationMatchForm, base_url="finance:reconciliations", template_dir="reconciliation_match")

ReportSnapshotViews = crud_views(model=ReportSnapshot, form_class=ReportSnapshotForm, base_url="finance:reports", template_dir="report_snapshot")