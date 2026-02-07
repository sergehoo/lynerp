from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from finance.models import AccountType, Account, Journal, CompanyFinanceProfile, AccountingStandard, Tax, TaxScope, \
    JournalType
from finance.models_base import Currency
from tenants.models import Tenant


SYSCOHADA_STARTER_ACCOUNTS = [
    # ====== CLASSE 1 : CAPITAUX ======
    ("101", "Capital", AccountType.EQUITY),
    ("106", "Réserves", AccountType.EQUITY),
    ("12", "Résultat net", AccountType.EQUITY),

    # ====== CLASSE 2 : IMMOBILISATIONS ======
    ("21", "Immobilisations incorporelles", AccountType.ASSET),
    ("22", "Terrains", AccountType.ASSET),
    ("23", "Bâtiments / constructions", AccountType.ASSET),
    ("24", "Matériel & outillage", AccountType.ASSET),
    ("28", "Amortissements", AccountType.ASSET),

    # ====== CLASSE 3 : STOCKS ======
    ("31", "Stocks de marchandises", AccountType.ASSET),
    ("32", "Stocks de matières", AccountType.ASSET),
    ("37", "Stocks - autres", AccountType.ASSET),

    # ====== CLASSE 4 : TIERS ======
    ("401", "Fournisseurs", AccountType.LIABILITY),
    ("404", "Fournisseurs d'immobilisations", AccountType.LIABILITY),
    ("408", "Fournisseurs - factures non parvenues", AccountType.LIABILITY),

    ("411", "Clients", AccountType.ASSET),
    ("418", "Clients - produits à recevoir", AccountType.ASSET),

    ("421", "Personnel - rémunérations dues", AccountType.LIABILITY),
    ("431", "Sécurité sociale / CNPS", AccountType.LIABILITY),

    ("4456", "TVA déductible", AccountType.ASSET),
    ("4457", "TVA collectée", AccountType.LIABILITY),
    ("447", "État - autres impôts & taxes", AccountType.LIABILITY),

    # ====== CLASSE 5 : TRÉSORERIE ======
    ("512", "Banques", AccountType.ASSET),
    ("531", "Caisse", AccountType.ASSET),
    ("57", "Caisse/banque - autres", AccountType.ASSET),

    # ====== CLASSE 6 : CHARGES ======
    ("601", "Achats de marchandises", AccountType.EXPENSE),
    ("602", "Achats de matières & fournitures", AccountType.EXPENSE),
    ("604", "Achats d'études & prestations", AccountType.EXPENSE),
    ("606", "Achats non stockés (eau, électricité, fournitures)", AccountType.EXPENSE),
    ("611", "Transports", AccountType.EXPENSE),
    ("612", "Voyages & déplacements", AccountType.EXPENSE),
    ("613", "Locations", AccountType.EXPENSE),
    ("614", "Charges locatives / copropriété", AccountType.EXPENSE),
    ("615", "Entretien & réparations", AccountType.EXPENSE),
    ("616", "Assurances", AccountType.EXPENSE),
    ("617", "Services bancaires", AccountType.EXPENSE),
    ("62", "Autres services extérieurs", AccountType.EXPENSE),
    ("63", "Impôts & taxes", AccountType.EXPENSE),
    ("64", "Charges de personnel", AccountType.EXPENSE),
    ("65", "Autres charges", AccountType.EXPENSE),

    # ====== CLASSE 7 : PRODUITS ======
    ("701", "Ventes de marchandises", AccountType.REVENUE),
    ("706", "Prestations de services", AccountType.REVENUE),
    ("707", "Ventes - autres", AccountType.REVENUE),
    ("75", "Autres produits", AccountType.REVENUE),
]


def _upsert_account(*, tenant: Tenant, code: str, name: str, acc_type: str) -> Account:
    obj, _ = Account.objects.update_or_create(
        tenant=tenant,
        code=code,
        defaults={"name": name, "type": acc_type, "is_active": True},
    )
    # Reconcilable defaults
    if code in {"401", "411", "512", "531"}:
        obj.is_reconcilable = True
        obj.save(update_fields=["is_reconcilable"])
    return obj


def _upsert_journal(*, tenant: Tenant, code: str, name: str, jtype: str, debit_code: str | None, credit_code: str | None):
    debit = Account.objects.filter(tenant=tenant, code=debit_code).first() if debit_code else None
    credit = Account.objects.filter(tenant=tenant, code=credit_code).first() if credit_code else None

    Journal.objects.update_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": name,
            "type": jtype,
            "is_active": True,
            "default_debit_account": debit,
            "default_credit_account": credit,
        },
    )


class Command(BaseCommand):
    help = "Seed SYSCOHADA starter chart of accounts, journals, and default VAT for one tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug (ex: acme)")
        parser.add_argument("--currency", default=Currency.XOF, help="Base currency (default XOF)")
        parser.add_argument("--vat", default="18.00", help="Default VAT rate (default 18.00)")

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["tenant"]
        currency = options["currency"]
        vat_rate = options["vat"]

        tenant = Tenant.objects.filter(slug=slug).first()
        if not tenant:
            raise CommandError(f"Tenant '{slug}' introuvable.")

        # Finance profile
        CompanyFinanceProfile.objects.update_or_create(
            tenant=tenant,
            defaults={
                "base_currency": currency,
                "standard": AccountingStandard.SYSCOHADA,
                "invoice_prefix": "INV",
                "bill_prefix": "BILL",
                "quote_prefix": "QT",
            },
        )

        # Accounts
        for code, name, acc_type in SYSCOHADA_STARTER_ACCOUNTS:
            _upsert_account(tenant=tenant, code=code, name=name, acc_type=acc_type)

        # Journals (avec comptes par défaut)
        _upsert_journal(tenant=tenant, code="VT", name="Journal des ventes", jtype=JournalType.SALES, debit_code="411", credit_code="701")
        _upsert_journal(tenant=tenant, code="AC", name="Journal des achats", jtype=JournalType.PURCHASE, debit_code="601", credit_code="401")
        _upsert_journal(tenant=tenant, code="BQ", name="Journal de banque", jtype=JournalType.BANK, debit_code="512", credit_code=None)
        _upsert_journal(tenant=tenant, code="CS", name="Journal de caisse", jtype=JournalType.CASH, debit_code="531", credit_code=None)
        _upsert_journal(tenant=tenant, code="OD", name="Opérations diverses", jtype=JournalType.GENERAL, debit_code=None, credit_code=None)

        # Taxes (TVA)
        tva_deduct = Account.objects.filter(tenant=tenant, code="4456").first()
        tva_collect = Account.objects.filter(tenant=tenant, code="4457").first()

        Tax.objects.update_or_create(
            tenant=tenant,
            name=f"TVA {vat_rate}%",
            defaults={
                "rate": vat_rate,
                "scope": TaxScope.BOTH,
                "is_active": True,
                "purchase_tax_account": tva_deduct,
                "sales_tax_account": tva_collect,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"SYSCOHADA starter seed OK for tenant='{tenant.slug}' (currency={currency}, VAT={vat_rate}%)."
        ))