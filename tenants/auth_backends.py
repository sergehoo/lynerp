"""
Backend d'authentification multi-tenant.

- Auth standard (login/password) avec ``ModelBackend``
- Vérifie ensuite que l'utilisateur dispose d'un ``TenantUser`` actif sur le
  tenant demandé. Si non : refus d'auth (le user ne peut pas se connecter
  sur un tenant auquel il n'appartient pas).
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from tenants.utils import get_user_membership, resolve_tenant

User = get_user_model()
logger = logging.getLogger(__name__)


class TenantModelBackend(ModelBackend):
    """
    Authentification Django classique enrichie d'un contrôle tenant.

    Le tenant peut être passé via :
    - ``request.POST['tenant_id']`` (formulaire)
    - ``kwargs['tenant_id']`` (programmatique)
    - ``request.tenant`` posé par le middleware
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None:
            return None

        tenant_identifier = None
        if request is not None:
            tenant_identifier = (
                request.POST.get("tenant_id")
                if hasattr(request, "POST")
                else None
            )
            if not tenant_identifier and getattr(request, "tenant", None) is not None:
                return self._verify_membership(user, request.tenant)

        tenant_identifier = tenant_identifier or kwargs.get("tenant_id")
        if not tenant_identifier:
            # Pas de contrainte tenant fournie ⇒ on délègue au middleware
            # (qui bloquera la requête si l'utilisateur n'a pas accès).
            return user

        tenant = resolve_tenant(tenant_identifier)
        if tenant is None:
            logger.warning(
                "[TenantModelBackend] Tenant inconnu '%s' pour user=%s",
                tenant_identifier,
                user.pk,
            )
            return None

        return self._verify_membership(user, tenant)

    @staticmethod
    def _verify_membership(user, tenant):
        if user.is_superuser:
            return user
        membership = get_user_membership(user, tenant)
        if membership is None:
            logger.info(
                "[TenantModelBackend] Refus : user=%s sans membership actif sur tenant=%s",
                user.pk,
                tenant.pk,
            )
            return None
        return user
