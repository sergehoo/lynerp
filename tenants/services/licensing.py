"""
Service de licensing LYNEERP.

Une licence (``tenants.License``) est rattachée à un tenant et porte un
``module`` (slug). On supporte deux granularités :

- ``module="all"`` : licence globale qui ouvre **tous** les modules.
- ``module="<slug>"`` : licence par module (ex. ``rh``, ``finance``,
  ``payroll``, ``ai`` …). Le check renvoie ``True`` si le tenant possède
  la licence du module demandé OU une licence ``all``.

Les fonctions sont des helpers purs : elles ne touchent pas la requête
HTTP ni la session. La couche DRF utilise ``HasModuleLicense`` (cf.
``tenants/permissions.py``).

Constantes :
- ``MODULE_ALL``  : "all"
- ``MODULES``     : liste canonique des slugs modules connus.
- ``ENFORCE_LICENSES`` : settings.LICENSE_ENFORCEMENT (défaut True).

Usage côté code :

    from tenants.services.licensing import has_license

    if not has_license(request.tenant, "ai"):
        raise PermissionDenied("Licence IA requise.")
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Iterable, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
MODULE_ALL = "all"

# Liste canonique : aligne-toi sur les slugs utilisés dans les URLs Django.
MODULES: List[str] = [
    "core",       # tâches, documents, audit système
    "hr",         # ressources humaines
    "payroll",    # paie
    "finance",    # comptabilité, factures, devis
    "crm",        # clients, opportunités
    "inventory",  # stock, achats
    "projects",   # gestion de projets
    "reporting",  # BI / exports
    "ocr",        # OCR factures
    "ai",         # assistant IA
    "admin",      # console d'administration
]


def _enforcement_enabled() -> bool:
    """Permet de désactiver complètement le check (dev local)."""
    return bool(getattr(settings, "LICENSE_ENFORCEMENT", True))


def _today() -> date:
    return timezone.now().date()


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #
def get_active_licenses(tenant) -> "list":
    """
    Retourne la liste des licences actives non expirées du tenant.
    Renvoie une liste vide si tenant=None.
    """
    if tenant is None:
        return []
    from tenants.models import License  # import tardif

    today = _today()
    return list(
        License.objects.filter(
            tenant=tenant,
            active=True,
            valid_until__gte=today,
        )
    )


def has_license(tenant, module: str) -> bool:
    """
    Renvoie True si le tenant possède une licence active couvrant ``module``.

    Couverture :
    - une licence ``module="all"`` couvre tout ;
    - une licence ``module=<slug>`` couvre uniquement ce slug.

    Si ``LICENSE_ENFORCEMENT`` est False (dev), retourne toujours True.
    Si ``tenant`` est None, retourne False (pas de licence sans tenant).
    """
    if not _enforcement_enabled():
        return True
    if tenant is None or not module:
        return False

    module = str(module).strip().lower()
    licenses = get_active_licenses(tenant)
    if not licenses:
        return False

    for lic in licenses:
        slug = (lic.module or "").strip().lower()
        if slug in (MODULE_ALL, module):
            return True
    return False


def licensed_modules(tenant) -> List[str]:
    """
    Liste les modules effectivement ouverts pour ce tenant.
    Si une licence ``all`` est présente, renvoie tous les modules connus.
    """
    if not _enforcement_enabled():
        return list(MODULES)
    licenses = get_active_licenses(tenant)
    if not licenses:
        return []
    slugs = {(lic.module or "").strip().lower() for lic in licenses}
    if MODULE_ALL in slugs:
        return list(MODULES)
    # ne renvoie que les slugs reconnus dans MODULES (filet anti-typos)
    return sorted(s for s in slugs if s in MODULES) or sorted(slugs)


def ensure_license(tenant, module: str) -> None:
    """
    Lève ``PermissionDenied`` si ``has_license`` est False.
    Pratique pour gating dans une vue Django classique.
    """
    if not has_license(tenant, module):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied(
            f"Licence requise pour le module « {module} ». "
            "Contactez votre administrateur."
        )


def grant_license(
    tenant,
    *,
    module: str = MODULE_ALL,
    plan: str = "ENTERPRISE",
    seats: int = 25,
    valid_for_days: int = 365,
) -> "License":
    """
    Crée (ou met à jour) une License pour ce tenant.

    Idempotent : si une licence pour ``(tenant, module)`` existe déjà,
    elle est mise à jour (plan, seats, valid_until, active=True).
    """
    from tenants.models import License

    valid_until = _today() + timezone.timedelta(days=valid_for_days)
    lic, created = License.objects.update_or_create(
        tenant=tenant,
        module=module.strip().lower(),
        defaults={
            "plan": plan,
            "seats": int(seats),
            "valid_until": valid_until,
            "active": True,
        },
    )
    logger.info(
        "License %s for tenant=%s module=%s plan=%s seats=%d valid_until=%s",
        "created" if created else "refreshed",
        tenant.slug if tenant else "?",
        lic.module, lic.plan, lic.seats, lic.valid_until,
    )
    return lic


def revoke_license(tenant, module: str) -> bool:
    """Désactive (active=False) la licence ``(tenant, module)``."""
    if tenant is None or not module:
        return False
    from tenants.models import License
    updated = License.objects.filter(
        tenant=tenant, module=module.strip().lower(),
    ).update(active=False)
    return bool(updated)
