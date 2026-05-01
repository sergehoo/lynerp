"""
Crée les workflows d'approbation standard pour un tenant :

- ``PO_APPROVAL``  : 2 étapes (Manager → Admin) pour un bon de commande > seuil.
- ``PAY_CLOSURE``  : clôture mensuelle paie (Manager paie + Direction).
- ``CONTRACT_SIGN``: signature contrat (RH + Direction).

Usage :
    python manage.py seed_workflows --tenant <slug|uuid>
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from tenants.models import Tenant
from workflows.models import ApprovalStep, ApprovalWorkflow

WORKFLOWS = [
    {
        "code": "PO_APPROVAL",
        "name": "Approbation bon de commande",
        "description": "Workflow standard d'approbation des bons de commande.",
        "target_model": "inventory.PurchaseOrder",
        "steps": [
            {"order": 1, "name": "Manager achats", "role_required": "MANAGER"},
            {"order": 2, "name": "Direction", "role_required": "ADMIN"},
        ],
    },
    {
        "code": "PAY_CLOSURE",
        "name": "Clôture mensuelle paie",
        "description": "Validation finale d'une période de paie avant clôture.",
        "target_model": "payroll.PayrollPeriod",
        "steps": [
            {"order": 1, "name": "Manager paie", "role_required": "MANAGER"},
            {"order": 2, "name": "Direction RH", "role_required": "ADMIN"},
        ],
    },
    {
        "code": "CONTRACT_SIGN",
        "name": "Signature contrat de travail",
        "description": "Validation juridique avant émission d'un contrat.",
        "target_model": "hr.EmploymentContract",
        "steps": [
            {"order": 1, "name": "RH", "role_required": "MANAGER"},
            {"order": 2, "name": "Direction", "role_required": "ADMIN"},
        ],
    },
]


class Command(BaseCommand):
    help = "Crée les workflows standards LYNEERP pour un tenant."

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

        created = 0
        for spec in WORKFLOWS:
            wf, was_created = ApprovalWorkflow.objects.get_or_create(
                tenant=tenant, code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "target_model": spec["target_model"],
                },
            )
            if was_created:
                created += 1
            for step in spec["steps"]:
                ApprovalStep.objects.get_or_create(
                    tenant=tenant, workflow=wf,
                    order=step["order"],
                    defaults={
                        "name": step["name"],
                        "role_required": step["role_required"],
                    },
                )
        self.stdout.write(self.style.SUCCESS(
            f"Seed workflows fait pour tenant {tenant.slug} ({created} nouveaux)."
        ))
