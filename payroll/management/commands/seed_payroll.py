"""
Commande Django : initialise les rubriques + profils OHADA pour un tenant.

Usage :
    python manage.py seed_payroll --tenant <slug|uuid>
    python manage.py seed_payroll --all                # tous les tenants actifs
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from payroll.services.seed import seed_ohada_payroll
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Initialise les rubriques et profils paie OHADA standards."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", help="Slug ou UUID du tenant cible.")
        parser.add_argument("--all", action="store_true", help="Tous les tenants actifs.")

    def handle(self, *args, **opts):
        if opts.get("all"):
            tenants = Tenant.objects.filter(is_active=True)
        elif opts.get("tenant"):
            t = (
                Tenant.objects.filter(slug=opts["tenant"]).first()
                or Tenant.objects.filter(id=opts["tenant"]).first()
            )
            if not t:
                raise CommandError(f"Tenant '{opts['tenant']}' introuvable.")
            tenants = [t]
        else:
            raise CommandError("Précisez --tenant <slug|uuid> ou --all.")

        for tenant in tenants:
            self.stdout.write(f"→ Tenant {tenant.slug} ({tenant.id})")
            result = seed_ohada_payroll(tenant)
            self.stdout.write(self.style.SUCCESS(
                f"   {len(result['created_items'])} nouvelles rubriques, "
                f"{len(result['created_profiles'])} nouveaux profils."
            ))
        self.stdout.write(self.style.SUCCESS("Done."))
