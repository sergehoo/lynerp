# compliance/admin.py
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    AuditEvent, CompanyFinanceProfile, FiscalYear, AccountingPeriod,
    Account, Journal, JournalEntry, JournalLine, Tax, FiscalClosing,
    ExchangeRate, Partner, Quote, QuoteLine, Invoice, InvoiceLine,
    Payment, SubscriptionPlan, Subscription, DunningStage, DunningEvent,
    CustomerPortalToken, VendorBill, VendorBillLine, ExpenseReport,
    ExpenseItem, PaymentOrder, PaymentOrderLine, BankConnector,
    BankAccount, BankTransaction, ReconciliationMatch, ReportSnapshot
)


# ============ INLINES ============
class JournalLineInline(TabularInline):
    model = JournalLine
    extra = 1
    fields = ('account', 'partner_label', 'label', 'debit', 'credit', 'currency')
    readonly_fields = ('currency',)


class QuoteLineInline(TabularInline):
    model = QuoteLine
    extra = 1
    fields = ('label', 'quantity', 'unit_price', 'tax', 'line_total', 'tax_amount')
    readonly_fields = ('line_total', 'tax_amount')


class InvoiceLineInline(TabularInline):
    model = InvoiceLine
    extra = 1
    fields = ('label', 'quantity', 'unit_price', 'tax', 'line_total', 'tax_amount')
    readonly_fields = ('line_total', 'tax_amount')


class VendorBillLineInline(TabularInline):
    model = VendorBillLine
    extra = 1
    fields = ('label', 'quantity', 'unit_price', 'tax', 'expense_account_code', 'line_total', 'tax_amount')
    readonly_fields = ('line_total', 'tax_amount')


class ExpenseItemInline(TabularInline):
    model = ExpenseItem
    extra = 1
    fields = ('date', 'label', 'category', 'amount', 'currency', 'tax', 'receipt')
    readonly_fields = ('ocr_text',)


class PaymentOrderLineInline(TabularInline):
    model = PaymentOrderLine
    extra = 1
    fields = ('bill', 'amount', 'currency', 'beneficiary_name', 'beneficiary_iban', 'reference')


class BankTransactionInline(TabularInline):
    model = BankTransaction
    extra = 0
    fields = ('date', 'label', 'amount', 'currency', 'status')
    readonly_fields = fields


# ============ FILTERS ============
class StatusFilter(admin.SimpleListFilter):
    title = 'statut'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Actif'),
            ('inactive', 'Inactif'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)


class DateRangeFilter(admin.SimpleListFilter):
    title = 'période'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return (
            ('today', "Aujourd'hui"),
            ('week', 'Cette semaine'),
            ('month', 'Ce mois'),
            ('quarter', 'Ce trimestre'),
            ('year', 'Cette année'),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'today':
            return queryset.filter(entry_date=today)
        elif self.value() == 'week':
            return queryset.filter(entry_date__week=today.isocalendar()[1],
                                   entry_date__year=today.year)
        elif self.value() == 'month':
            return queryset.filter(entry_date__month=today.month,
                                   entry_date__year=today.year)
        elif self.value() == 'quarter':
            quarter = (today.month - 1) // 3 + 1
            return queryset.filter(entry_date__quarter=quarter,
                                   entry_date__year=today.year)
        elif self.value() == 'year':
            return queryset.filter(entry_date__year=today.year)


# ============ MODEL ADMINS ============
@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'model_label', 'object_id', 'tenant')
    list_filter = ('action', 'model_label', 'created_at')
    search_fields = ('object_id', 'object_repr', 'actor__email', 'actor__username')
    readonly_fields = ('created_at', 'prev_hash', 'event_hash', 'before', 'after', 'meta')
    fieldsets = (
        ('Événement', {
            'fields': ('actor', 'action', 'model_label', 'object_id', 'object_repr', 'created_at')
        }),
        ('Données', {
            'fields': ('before', 'after', 'meta'),
            'classes': ('collapse',)
        }),
        ('Hash Chain', {
            'fields': ('prev_hash', 'event_hash'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(CompanyFinanceProfile)
class CompanyFinanceProfileAdmin(ModelAdmin):
    list_display = ('tenant', 'base_currency', 'standard', 'lock_posted_entries')
    list_filter = ('standard', 'lock_posted_entries')
    fieldsets = (
        ('Configuration', {
            'fields': ('tenant', 'base_currency', 'standard')
        }),
        ('Numérotation', {
            'fields': ('invoice_prefix', 'bill_prefix', 'quote_prefix'),
            'classes': ('collapse',)
        }),
        ('Options', {
            'fields': ('lock_posted_entries', 'require_attachments_for_expenses')
        }),
    )


@admin.register(FiscalYear)
class FiscalYearAdmin(ModelAdmin):
    list_display = ('name', 'tenant', 'date_start', 'date_end', 'is_closed', 'periods_count')
    list_filter = ('is_closed', 'tenant')
    search_fields = ('name',)
    readonly_fields = ('periods_count',)

    def periods_count(self, obj):
        return obj.periods.count()

    periods_count.short_description = 'Périodes'


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(ModelAdmin):
    list_display = ('name', 'fiscal_year', 'date_start', 'date_end', 'status', 'tenant')
    list_filter = ('status', 'fiscal_year', 'tenant')
    search_fields = ('name',)
    list_editable = ('status',)
    actions = ['close_period', 'lock_period']

    def close_period(self, request, queryset):
        updated = queryset.update(status='CLOSED')
        self.message_user(request, f"{updated} période(s) clôturée(s).")

    close_period.short_description = "Clôturer les périodes sélectionnées"

    def lock_period(self, request, queryset):
        updated = queryset.update(status='LOCKED')
        self.message_user(request, f"{updated} période(s) verrouillée(s).")

    lock_period.short_description = "Verrouiller les périodes sélectionnées"


@admin.register(Account)
class AccountAdmin(ModelAdmin):
    list_display = ('code', 'name', 'type', 'parent', 'is_active', 'tenant')
    list_filter = ('type', 'is_active', 'is_reconcilable', StatusFilter)
    search_fields = ('code', 'name')
    list_editable = ('is_active',)
    fieldsets = (
        ('Identification', {
            'fields': ('tenant', 'code', 'name', 'type', 'parent')
        }),
        ('Configuration', {
            'fields': ('is_active', 'is_reconcilable', 'allow_manual')
        }),
    )
    autocomplete_fields = ('parent',)


@admin.register(Journal)
class JournalAdmin(ModelAdmin):
    list_display = ('code', 'name', 'type', 'is_active', 'tenant')
    list_filter = ('type', 'is_active', StatusFilter)
    search_fields = ('code', 'name')
    list_editable = ('is_active',)
    fieldsets = (
        ('Identification', {
            'fields': ('tenant', 'code', 'name', 'type')
        }),
        ('Comptes par défaut', {
            'fields': ('default_debit_account', 'default_credit_account'),
            'classes': ('collapse',)
        }),
        ('État', {
            'fields': ('is_active',)
        }),
    )
    autocomplete_fields = ('default_debit_account', 'default_credit_account')


@admin.register(JournalEntry)
class JournalEntryAdmin(ModelAdmin):
    list_display = ('reference', 'journal', 'entry_date', 'period', 'status', 'total_debit', 'total_credit', 'tenant')
    list_filter = ('status', 'journal', 'period', DateRangeFilter, 'tenant')
    search_fields = ('reference', 'label', 'source_object_id')
    readonly_fields = ('total_debit', 'total_credit', 'is_balanced')
    inlines = [JournalLineInline]
    fieldsets = (
        ('En-tête', {
            'fields': ('journal', 'period', 'entry_date', 'status')
        }),
        ('Référence', {
            'fields': ('reference', 'label')
        }),
        ('Source', {
            'fields': ('source_model', 'source_object_id'),
            'classes': ('collapse',)
        }),
        ('Totaux', {
            'fields': ('total_debit', 'total_credit', 'is_balanced'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'entry_date'
    actions = ['post_entries', 'cancel_entries']

    def post_entries(self, request, queryset):
        for entry in queryset.filter(status='DRAFT'):
            entry.status = 'POSTED'
            entry.save()
        self.message_user(request, f"{queryset.count()} écriture(s) comptabilisée(s).")

    post_entries.short_description = "Comptabiliser les écritures sélectionnées"

    def cancel_entries(self, request, queryset):
        for entry in queryset.filter(status='DRAFT'):
            entry.status = 'CANCELLED'
            entry.save()
        self.message_user(request, f"{queryset.count()} écriture(s) annulée(s).")

    cancel_entries.short_description = "Annuler les écritures sélectionnées"


@admin.register(Tax)
class TaxAdmin(ModelAdmin):
    list_display = ('name', 'rate', 'scope', 'is_active', 'tenant')
    list_filter = ('scope', 'is_active', StatusFilter)
    search_fields = ('name',)
    list_editable = ('is_active', 'rate')
    fieldsets = (
        ('Taux', {
            'fields': ('tenant', 'name', 'rate', 'scope')
        }),
        ('Comptes associés', {
            'fields': ('sales_tax_account', 'purchase_tax_account'),
            'classes': ('collapse',)
        }),
        ('État', {
            'fields': ('is_active',)
        }),
    )
    autocomplete_fields = ('sales_tax_account', 'purchase_tax_account')


@admin.register(FiscalClosing)
class FiscalClosingAdmin(ModelAdmin):
    list_display = ('fiscal_year', 'status', 'generated_at', 'posted_at', 'tenant')
    list_filter = ('status', 'tenant')
    readonly_fields = ('generated_at', 'posted_at')
    fieldsets = (
        ('Clôture', {
            'fields': ('fiscal_year', 'status', 'notes')
        }),
        ('Écritures', {
            'fields': ('closing_entry', 'opening_entry_next_fy'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('generated_at', 'posted_at'),
            'classes': ('collapse',)
        }),
    )
    autocomplete_fields = ('closing_entry', 'opening_entry_next_fy')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(ModelAdmin):
    list_display = ('date', 'base_currency', 'quote_currency', 'rate', 'source', 'is_locked', 'tenant')
    list_filter = ('base_currency', 'quote_currency', 'is_locked', 'tenant')
    search_fields = ('source',)
    list_editable = ('rate', 'is_locked')
    date_hierarchy = 'date'
    fieldsets = (
        ('Taux', {
            'fields': ('date', 'base_currency', 'quote_currency', 'rate')
        }),
        ('Métadonnées', {
            'fields': ('source', 'is_locked')
        }),
    )


@admin.register(Partner)
class PartnerAdmin(ModelAdmin):
    list_display = ('code', 'name', 'type', 'email', 'phone', 'is_active', 'tenant')
    list_filter = ('type', 'is_active', StatusFilter)
    search_fields = ('code', 'name', 'email', 'vat_number')
    list_editable = ('is_active',)
    fieldsets = (
        ('Identification', {
            'fields': ('tenant', 'code', 'name', 'type', 'vat_number')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address')
        }),
        ('État', {
            'fields': ('is_active',)
        }),
    )


def get_request_tenant(request):
    # middleware: request.tenant
    t = getattr(request, "tenant", None)
    if t:
        return t
    # fallback dev: header
    slug = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
    if slug:
        from tenants.models import Tenant
        return Tenant.objects.filter(slug=slug, is_active=True).first()
    return None

class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 1

    def save_new_instance(self, request, obj, form, change):
        # pas appelé par défaut, donc on gère via save_formset plus bas
        super().save_new_instance(request, obj, form, change)

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    inlines = [QuoteLineInline]
    list_display = ("number", "tenant", "partner", "status", "issue_date")

    def save_model(self, request, obj, form, change):
        if not obj.tenant_id:
            tenant = get_request_tenant(request)
            if not tenant:
                raise ValidationError("Tenant non résolu. En admin, envoie X-Tenant-Id ou définis request.tenant.")
            obj.tenant = tenant
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        Important: les QuoteLine héritent aussi de TenantOwnedModel => tenant obligatoire.
        """
        instances = formset.save(commit=False)

        # le parent quote est déjà sauvé ici
        quote = form.instance
        for inst in instances:
            if hasattr(inst, "tenant_id") and not inst.tenant_id:
                inst.tenant = quote.tenant
            formset.save_m2m()
            inst.save()

        # suppressions
        for obj in formset.deleted_objects:
            obj.delete()


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('number', 'partner', 'type', 'status', 'issue_date', 'due_date',
                    'total', 'amount_paid', 'amount_due', 'tenant')
    list_filter = ('type', 'status', 'issue_date', 'tenant')
    search_fields = ('number', 'partner__name', 'partner__code')
    readonly_fields = ('subtotal', 'total_tax', 'total', 'amount_paid', 'amount_due')
    inlines = [InvoiceLineInline]
    fieldsets = (
        ('Facture', {
            'fields': ('number', 'partner', 'type', 'status', 'issue_date', 'due_date')
        }),
        ('Référence', {
            'fields': ('quote', 'journal_entry_id'),
            'classes': ('collapse',)
        }),
        ('Montants', {
            'fields': ('currency', 'subtotal', 'total_tax', 'total',
                       'amount_paid', 'amount_due', 'notes')
        }),
        ('Communication', {
            'fields': ('pdf_file', 'sent_at'),
            'classes': ('collapse',)
        }),
        ('Verrouillage', {
            'fields': ('lock_owner', 'lock_at'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'issue_date'
    actions = ['mark_as_sent', 'mark_as_paid']

    def mark_as_sent(self, request, queryset):
        updated = queryset.update(sent_at=timezone.now())
        self.message_user(request, f"{updated} facture(s) marquée(s) comme envoyées.")

    mark_as_sent.short_description = "Marquer comme envoyé"

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='PAID')
        self.message_user(request, f"{updated} facture(s) marquée(s) comme payées.")

    mark_as_paid.short_description = "Marquer comme payé"


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('invoice', 'method', 'status', 'amount', 'currency', 'paid_at', 'reference', 'tenant')
    list_filter = ('method', 'status', 'paid_at', 'tenant')
    search_fields = ('reference', 'invoice__number', 'provider')
    readonly_fields = ('provider_payload',)
    fieldsets = (
        ('Paiement', {
            'fields': ('invoice', 'method', 'status', 'amount', 'currency', 'paid_at', 'reference')
        }),
        ('Provider', {
            'fields': ('provider', 'provider_payload', 'journal_entry_id'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'paid_at'


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ('name', 'amount', 'currency', 'interval_count', 'interval_unit', 'is_active', 'tenant')
    list_filter = ('interval_unit', 'is_active', StatusFilter)
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'amount')
    fieldsets = (
        ('Abonnement', {
            'fields': ('tenant', 'name', 'description')
        }),
        ('Tarification', {
            'fields': ('amount', 'currency', 'interval_count', 'interval_unit')
        }),
        ('État', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('partner', 'plan', 'status', 'start_date', 'end_date',
                    'next_invoice_date', 'tenant')
    list_filter = ('status', 'plan', 'start_date', 'tenant')
    search_fields = ('partner__name', 'partner__code')
    readonly_fields = ('last_invoiced_at',)
    fieldsets = (
        ('Abonnement', {
            'fields': ('partner', 'plan', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'next_invoice_date', 'last_invoiced_at')
        }),
        ('Métadonnées', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'start_date'


@admin.register(VendorBill)
class VendorBillAdmin(ModelAdmin):
    list_display = ('number', 'supplier', 'status', 'bill_date', 'due_date',
                    'total', 'validated_by', 'tenant')
    list_filter = ('status', 'bill_date', 'tenant')
    search_fields = ('number', 'supplier__name', 'supplier__code')
    readonly_fields = ('subtotal', 'total_tax', 'total', 'ocr_text', 'ocr_json', 'parsed_json')
    inlines = [VendorBillLineInline]
    fieldsets = (
        ('Facture fournisseur', {
            'fields': ('number', 'supplier', 'status', 'bill_date', 'due_date')
        }),
        ('Montants', {
            'fields': ('currency', 'subtotal', 'total_tax', 'total', 'notes')
        }),
        ('OCR', {
            'fields': ('document', 'ocr_text', 'ocr_json', 'parsed_json'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('validated_by', 'validated_at', 'journal_entry_id'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'bill_date'


@admin.register(ExpenseReport)
class ExpenseReportAdmin(ModelAdmin):
    list_display = ('title', 'employee_id', 'status', 'submitted_at', 'total_amount', 'tenant')
    list_filter = ('status', 'submitted_at', 'tenant')
    search_fields = ('title', 'employee_id', 'notes')
    readonly_fields = ('total_amount',)
    inlines = [ExpenseItemInline]

    def total_amount(self, obj):
        total = obj.items.aggregate(total=Sum('amount'))['total'] or 0
        return f"{total:,.2f}"

    total_amount.short_description = 'Montant total'

    fieldsets = (
        ('Note de frais', {
            'fields': ('employee_id', 'title', 'status', 'notes')
        }),
        ('Validation', {
            'fields': ('submitted_at', 'approved_by_manager', 'approved_by_finance'),
            'classes': ('collapse',)
        }),
        ('Comptabilité', {
            'fields': ('journal_entry_id',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentOrder)
class PaymentOrderAdmin(ModelAdmin):
    list_display = ('name', 'status', 'total_amount', 'created_by', 'tenant')
    list_filter = ('status', 'tenant')
    search_fields = ('name', 'created_by__email')
    readonly_fields = ('total_amount', 'generated_file')
    inlines = [PaymentOrderLineInline]
    fieldsets = (
        ('Ordre de paiement', {
            'fields': ('name', 'status', 'created_by')
        }),
        ('Fichier', {
            'fields': ('generated_file', 'total_amount'),
            'classes': ('collapse',)
        }),
        ('Paramètres', {
            'fields': ('meta',),
            'classes': ('collapse',)
        }),
    )
    actions = ['generate_payment_file']

    def generate_payment_file(self, request, queryset):
        # Logique de génération de fichier SEPA/autres
        self.message_user(request, f"Génération lancée pour {queryset.count()} ordre(s).")

    generate_payment_file.short_description = "Générer fichier de paiement"


@admin.register(BankConnector)
class BankConnectorAdmin(ModelAdmin):
    list_display = ('name', 'provider', 'is_active', 'last_sync_at', 'tenant')
    list_filter = ('provider', 'is_active', StatusFilter)
    search_fields = ('name',)
    readonly_fields = ('last_sync_at', 'credentials')
    fieldsets = (
        ('Connecteur', {
            'fields': ('tenant', 'name', 'provider', 'is_active')
        }),
        ('Synchronisation', {
            'fields': ('last_sync_at',),
            'classes': ('collapse',)
        }),
        ('Identifiants', {
            'fields': ('credentials',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BankAccount)
class BankAccountAdmin(ModelAdmin):
    list_display = ('name', 'connector', 'currency', 'iban', 'is_active', 'tenant')
    list_filter = ('currency', 'is_active', StatusFilter)
    search_fields = ('name', 'iban', 'external_id')
    list_editable = ('is_active',)
    inlines = [BankTransactionInline]
    fieldsets = (
        ('Compte bancaire', {
            'fields': ('connector', 'name', 'currency', 'is_active')
        }),
        ('Coordonnées', {
            'fields': ('iban', 'bic', 'external_id'),
            'classes': ('collapse',)
        }),
        ('Comptabilité', {
            'fields': ('gl_account_code',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BankTransaction)
class BankTransactionAdmin(ModelAdmin):
    list_display = ('date', 'bank_account', 'label', 'amount', 'currency', 'status', 'tenant')
    list_filter = ('status', 'currency', 'date', 'tenant')
    search_fields = ('label', 'external_id')
    readonly_fields = ('raw',)
    fieldsets = (
        ('Transaction', {
            'fields': ('bank_account', 'date', 'label', 'amount', 'currency', 'status')
        }),
        ('Identification', {
            'fields': ('external_id',),
            'classes': ('collapse',)
        }),
        ('Données brutes', {
            'fields': ('raw',),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'date'
    actions = ['match_transactions']

    def match_transactions(self, request, queryset):
        # Logique de rapprochement automatique
        self.message_user(request, f"Rapprochement lancé pour {queryset.count()} transaction(s).")

    match_transactions.short_description = "Rapprocher automatiquement"


@admin.register(ReconciliationMatch)
class ReconciliationMatchAdmin(ModelAdmin):
    list_display = ('bank_transaction', 'match_type', 'target_model', 'confidence', 'matched_at', 'tenant')
    list_filter = ('match_type', 'matched_at', 'tenant')
    search_fields = ('target_object_id', 'bank_transaction__label')
    readonly_fields = ('matched_at', 'meta')
    fieldsets = (
        ('Rapprochement', {
            'fields': ('bank_transaction', 'match_type', 'confidence')
        }),
        ('Cible', {
            'fields': ('target_model', 'target_object_id'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('matched_at', 'meta'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportSnapshot)
class ReportSnapshotAdmin(ModelAdmin):
    list_display = ('report_type', 'generated_at', 'generated_by_id', 'has_file', 'tenant')
    list_filter = ('report_type', 'generated_at', 'tenant')
    search_fields = ('generated_by_id',)
    readonly_fields = ('generated_at', 'data', 'file')

    def has_file(self, obj):
        return bool(obj.file)

    has_file.boolean = True
    has_file.short_description = 'Fichier'

    fieldsets = (
        ('Rapport', {
            'fields': ('report_type', 'generated_at', 'generated_by_id')
        }),
        ('Paramètres', {
            'fields': ('params',),
            'classes': ('collapse',)
        }),
        ('Résultats', {
            'fields': ('data', 'file'),
            'classes': ('collapse',)
        }),
    )


# ============ DASHBOARD & CUSTOM VIEWS ============
class FinanceAdminSite(admin.AdminSite):
    site_header = "Administration Finance & Comptabilité"
    site_title = "Système de Gestion Financière"
    index_title = "Tableau de bord"

    def get_app_list(self, request):
        app_list = super().get_app_list(request)

        # Personnaliser l'ordre des apps si nécessaire
        for app in app_list:
            if app['app_label'] == 'compliance':
                # Réorganiser les modèles dans l'ordre logique
                models_order = [
                    'CompanyFinanceProfile',
                    'FiscalYear',
                    'AccountingPeriod',
                    'Account',
                    'Journal',
                    'JournalEntry',
                    'Tax',
                    'Partner',
                    'Invoice',
                    'Payment',
                    'Quote',
                    'VendorBill',
                    'ExpenseReport',
                    'PaymentOrder',
                    'SubscriptionPlan',
                    'Subscription',
                    'BankAccount',
                    'BankTransaction',
                    'ReconciliationMatch',
                    'ExchangeRate',
                    'FiscalClosing',
                    'ReportSnapshot',
                    'AuditEvent',
                    'DunningStage',
                    'CustomerPortalToken',
                ]

                # Trier les modèles selon l'ordre défini
                app['models'].sort(key=lambda x: models_order.index(x['object_name'])
                if x['object_name'] in models_order else 999)

        return app_list

# Optionnel: Créer un site admin dédié pour le module finance
# finance_admin_site = FinanceAdminSite(name='finance_admin')
# Ensuite enregistrer tous les modèles avec finance_admin_site au lieu de admin.site

# Pour utiliser le site admin dédié, ajouter dans urls.py:
# urlpatterns += [path('finance-admin/', finance_admin_site.urls)]
@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message')
    list_filter = ('action_time', 'content_type', 'action_flag')
    search_fields = ('user__username', 'object_repr', 'change_message')
    date_hierarchy = 'action_time'
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id',
                      'object_repr', 'action_flag', 'change_message')
