"""
Permissions DRF basées sur le licensing LYNEERP.

Usage :

    from tenants.permissions import HasModuleLicense

    class HRViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, HasModuleLicense]
        license_module = "hr"

Le module est lu dans l'attribut ``license_module`` du viewset/vue.
À défaut, on tente de l'inférer depuis ``request.resolver_match.namespace``
(``hr_api`` → ``hr``, etc.).

La permission est satisfaite si :

1. Le tenant courant existe (``request.tenant``).
2. La licence ``module=ALL`` ou ``module=<slug>`` est active et non expirée.
3. ``settings.LICENSE_ENFORCEMENT`` est False (dev) → bypass total.
"""
from __future__ import annotations

import logging
from typing import Optional

from rest_framework.permissions import BasePermission

from tenants.services.licensing import has_license

logger = logging.getLogger(__name__)


def _infer_module(view, request) -> Optional[str]:
    """
    Essaie de détecter le module métier de la vue.

    Ordre :
    1. Attribut ``license_module`` sur la vue (recommandé).
    2. Attribut ``module`` sur la vue.
    3. Namespace du resolver (``hr_api`` → ``hr``, ``finance`` → ``finance``).
    """
    candidate = getattr(view, "license_module", None) or getattr(view, "module", None)
    if candidate:
        return str(candidate).strip().lower()

    rm = getattr(request, "resolver_match", None)
    if rm and rm.namespace:
        ns = rm.namespace.split(":")[-1]
        # Heuristique : on supprime le suffixe _api éventuel.
        return ns.replace("_api", "").strip().lower() or None
    return None


class HasModuleLicense(BasePermission):
    """
    Autorise la requête si le tenant a une licence active pour le module ciblé.
    """

    message = "Licence absente ou expirée pour ce module."

    def has_permission(self, request, view) -> bool:
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            # Le middleware bloque déjà ce cas pour les routes /api/, mais
            # on garde une ceinture de sécurité.
            self.message = "Aucune organisation associée à votre session."
            return False

        module = _infer_module(view, request)
        if not module:
            # Aucune indication explicite : on laisse passer (la vue n'a pas
            # déclaré de gating). Mieux que de bloquer arbitrairement.
            return True

        ok = has_license(tenant, module)
        if not ok:
            logger.info(
                "License denied tenant=%s module=%s user=%s",
                getattr(tenant, "slug", tenant), module,
                getattr(request.user, "email", request.user),
            )
            self.message = (
                f"Licence absente ou expirée pour le module « {module} »."
            )
        return ok


class IsTenantOwnerOrAdmin(BasePermission):
    """
    Réservé aux OWNER/ADMIN du tenant courant. Pratique pour les écrans
    de gestion (utilisateurs, licences, paramètres).
    """

    message = "Réservé aux administrateurs de l'organisation."

    def has_permission(self, request, view) -> bool:
        tenant = getattr(request, "tenant", None)
        user = getattr(request, "user", None)
        if tenant is None or user is None or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        from tenants.models import TenantUser
        return TenantUser.objects.filter(
            tenant=tenant, user=user, is_active=True,
            role__in=["OWNER", "ADMIN"],
        ).exists()
