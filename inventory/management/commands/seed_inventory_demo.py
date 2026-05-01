"""
Seed minimal de démonstration pour le module Stock.

Crée pour un tenant donné :
- un entrepôt par défaut "MAIN"
- une catégorie "Général"
- 5 articles de test avec seuils min/max
- un fournisseur démo

Idempotent : ne touche pas aux objets existants.

Usage:
    python manage.py seed_inventory_demo --tenant <slug|uuid>
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from inventory.models import Article, ArticleCategory, Supplier, Warehouse
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Crée un jeu de données minimal pour le module Stock."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Slug ou UUID du tenant.")

    def handle(self, *args, **opts):
        ident = opts["tenant"]
        tenant = (
            Tenant.objects.filter(slug=ident).first()
            or Tenant.objects.filter(id=ident).first()
        )
        if not tenant:
            raise CommandError(f"Tenant '{ident}' introuvable.")

        # Entrepôt
        wh, _ = Warehouse.objects.get_or_create(
            tenant=tenant, code="MAIN",
            defaults={"name": "Entrepôt principal"},
        )
        # Catégorie
        cat, _ = ArticleCategory.objects.get_or_create(
            tenant=tenant, code="GEN",
            defaults={"name": "Général"},
        )
        # Articles
        seed_articles = [
            {"sku": "ART-001", "name": "Ramette papier A4", "purchase_price": "2500", "sale_price": "3500", "min_stock": "20", "max_stock": "200"},
            {"sku": "ART-002", "name": "Toner imprimante laser", "purchase_price": "35000", "sale_price": "45000", "min_stock": "5", "max_stock": "30"},
            {"sku": "ART-003", "name": "Stylo bille (boîte de 50)", "purchase_price": "5000", "sale_price": "7000", "min_stock": "10", "max_stock": "100"},
            {"sku": "ART-004", "name": "Câble HDMI 2m", "purchase_price": "3500", "sale_price": "5000", "min_stock": "10", "max_stock": "50"},
            {"sku": "ART-005", "name": "Disque dur SSD 500Go", "purchase_price": "45000", "sale_price": "65000", "min_stock": "5", "max_stock": "30"},
        ]
        for spec in seed_articles:
            Article.objects.get_or_create(
                tenant=tenant, sku=spec["sku"],
                defaults={
                    "name": spec["name"],
                    "category": cat,
                    "purchase_price": Decimal(spec["purchase_price"]),
                    "sale_price": Decimal(spec["sale_price"]),
                    "min_stock": Decimal(spec["min_stock"]),
                    "max_stock": Decimal(spec["max_stock"]),
                    "currency": getattr(tenant, "currency", "XOF"),
                },
            )

        # Fournisseur démo
        Supplier.objects.get_or_create(
            tenant=tenant, code="SUPP-001",
            defaults={
                "name": "Fournisseur Démo",
                "email": "supplier@demo.local",
                "payment_terms_days": 30,
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"Seed inventaire fait pour tenant {tenant.slug} : "
            f"1 entrepôt, 1 catégorie, {len(seed_articles)} articles, 1 fournisseur."
        ))
