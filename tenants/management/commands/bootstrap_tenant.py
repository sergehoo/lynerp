"""
Commande de bootstrap pour LYNEERP.

Crée (ou met à jour de manière idempotente) :

1. Un Tenant avec le slug demandé.
2. Une License ``module=ALL`` plan ``ENTERPRISE`` valide 365j.
3. Une membership ``TenantUser`` (rôle OWNER par défaut) pour
   l'utilisateur identifié par son email.

Cas d'usage typique :

    # Premier déploiement local — débloque l'utilisateur connecté
    python manage.py bootstrap_tenant \\
        --slug kaydan \\
        --name "Kaydan Groupe" \\
        --owner-email serge.ogah@kaydangroupe.com

    # En production : juste l'organisation, sans owner
    python manage.py bootstrap_tenant --slug acme --name "ACME SA"

Si l'utilisateur n'existe pas, il est créé (sans mot de passe — il
devra passer par le SSO Keycloak ou un reset). On peut aussi le forcer
superuser avec ``--superuser``.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Bootstrap un tenant LYNEERP : crée (idempotent) le Tenant, une "
        "License 'all' Enterprise 365j, et une membership OWNER pour un "
        "utilisateur."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--slug", required=True, help="Slug du tenant (ex: kaydan).")
        parser.add_argument("--name", required=True, help="Nom affiché du tenant.")
        parser.add_argument(
            "--owner-email",
            help="Email du user à promouvoir OWNER. Crée le user si absent.",
        )
        parser.add_argument(
            "--module",
            default="all",
            help="Module de la licence (default: all).",
        )
        parser.add_argument(
            "--plan",
            default="ENTERPRISE",
            help="Plan de la licence (default: ENTERPRISE).",
        )
        parser.add_argument(
            "--seats",
            type=int,
            default=25,
            help="Nombre de sièges (default: 25).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Validité de la licence en jours (default: 365).",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Promeut l'utilisateur en superuser Django.",
        )
        parser.add_argument(
            "--role",
            default="OWNER",
            choices=["OWNER", "ADMIN", "MANAGER", "MEMBER", "VIEWER", "HR_BPO"],
            help="Rôle de la membership (default: OWNER).",
        )

    @transaction.atomic
    def handle(self, *args, **opts) -> None:
        from tenants.models import Tenant, TenantUser
        from tenants.services.licensing import grant_license

        slug = opts["slug"].strip().lower()
        name = opts["name"].strip()

        # 1) Tenant
        tenant, created = Tenant.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "is_active": True,
            },
        )
        if not created and tenant.name != name:
            tenant.name = name
            tenant.save(update_fields=["name"])
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Found'} tenant: {tenant.slug} ({tenant.name})"
        ))

        # 2) License
        lic = grant_license(
            tenant,
            module=opts["module"],
            plan=opts["plan"],
            seats=opts["seats"],
            valid_for_days=opts["days"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"License: module={lic.module} plan={lic.plan} "
            f"seats={lic.seats} valid_until={lic.valid_until}"
        ))

        # 3) Owner
        owner_email = (opts.get("owner_email") or "").strip().lower()
        if not owner_email:
            self.stdout.write(self.style.WARNING(
                "Aucun --owner-email fourni : pas de membership créée."
            ))
            return

        user = (
            User.objects.filter(email__iexact=owner_email).first()
            or User.objects.filter(username__iexact=owner_email).first()
        )
        if user is None:
            user = User.objects.create(
                username=owner_email, email=owner_email, is_active=True,
            )
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"User créé : {owner_email} (mot de passe inutilisable, SSO requis)."
            ))
        else:
            self.stdout.write(f"User trouvé : {user.email or user.username}.")

        if opts["superuser"] and not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=["is_superuser", "is_staff"])
            self.stdout.write(self.style.WARNING("User promu superuser Django."))

        membership, m_created = TenantUser.objects.get_or_create(
            tenant=tenant, user=user,
            defaults={"role": opts["role"], "is_active": True},
        )
        if not m_created:
            membership.role = opts["role"]
            membership.is_active = True
            membership.save(update_fields=["role", "is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"Membership {'créée' if m_created else 'mise à jour'} : "
            f"{user.email} → {tenant.slug} ({membership.role})"
        ))
        self.stdout.write(self.style.SUCCESS(
            "✔ Bootstrap terminé. Reconnecte-toi : tu devrais accéder à /ai/."
        ))
