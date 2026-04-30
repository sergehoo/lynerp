"""
Mixins et permissions DRF mutualisés pour LYNEERP.

Implémente une isolation multi-tenant systématique :

- ``TenantQuerysetMixin`` filtre automatiquement le queryset d'un viewset DRF
  ou d'une CBV Django sur ``request.tenant``.
- ``TenantOwnedDetailMixin`` à utiliser sur les CBV ``DetailView``/``UpdateView``/
  ``DeleteView`` pour empêcher l'accès cross-tenant via PK.
- ``HasTenantMembership`` est une permission DRF qui vérifie que l'utilisateur
  authentifié appartient bien au tenant courant.
- ``HasTenantRole`` étend la précédente avec un check de rôles.
"""
from __future__ import annotations

import logging
from typing import Iterable, Set

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework.permissions import SAFE_METHODS, BasePermission

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _request_tenant(request):
    """
    Retourne l'objet Tenant attaché à la requête (via le middleware).

    Si rien n'a été posé, on tente une résolution paresseuse.
    """
    from Lyneerp.core.tenant import resolve_tenant_from_request

    tenant = getattr(request, "tenant", None)
    if tenant is None:
        tenant = resolve_tenant_from_request(request)
        try:
            request.tenant = tenant
        except Exception:  # pragma: no cover - request peut être immutable
            pass
    return tenant


def _user_is_platform_admin(user) -> bool:
    """Super-admin global LYNEERP : accès cross-tenant."""
    if not user or not user.is_authenticated:
        return False
    return bool(getattr(user, "is_superuser", False))


def _membership(user, tenant):
    if not user or not user.is_authenticated or tenant is None:
        return None
    try:
        from tenants.models import TenantUser
    except Exception:  # noqa: BLE001
        return None
    return (
        TenantUser.objects
        .filter(user=user, tenant=tenant, is_active=True)
        .select_related("tenant")
        .first()
    )


def _user_roles(request) -> Set[str]:
    """
    Union des rôles : Keycloak (realm + client) + TenantUser.role.
    """
    roles: Set[str] = set()

    # JWT (request.auth posé par DRF Authenticator Keycloak)
    payload = getattr(request, "auth", None) or {}
    if isinstance(payload, dict):
        from django.conf import settings

        client = getattr(settings, "KEYCLOAK_CLIENT_ID", "rh-core")
        roles.update(payload.get("realm_access", {}).get("roles", []) or [])
        roles.update(payload.get("resource_access", {}).get(client, {}).get("roles", []) or [])

    # Session OIDC mémorisée
    if hasattr(request, "session"):
        from django.conf import settings

        oidc_key = getattr(settings, "OIDC_SESSION_KEY", "oidc_user")
        sess = request.session.get(oidc_key, {}) or {}
        roles.update(sess.get("roles") or [])

    # Membership tenant
    membership = _membership(getattr(request, "user", None), getattr(request, "tenant", None))
    if membership and membership.role:
        roles.add(membership.role.upper())

    return roles


# --------------------------------------------------------------------------- #
# Mixins de QuerySet (CBV + DRF)
# --------------------------------------------------------------------------- #
class TenantQuerysetMixin:
    """
    Filtre toujours le queryset par tenant courant.

    À utiliser sur des viewsets DRF qui héritent de ``GenericViewSet`` ou sur
    des CBV Django (``ListView``, ``DetailView`` etc.). Si l'utilisateur est
    superuser, le filtre est levé (mais on log).
    """

    tenant_field = "tenant"

    def get_queryset(self):
        qs = super().get_queryset()
        request = getattr(self, "request", None)
        if request is None:
            return qs.none()

        if _user_is_platform_admin(request.user):
            return qs

        tenant = _request_tenant(request)
        if tenant is None:
            logger.warning(
                "[TenantQuerysetMixin] Pas de tenant résolu pour user=%s path=%s",
                getattr(request.user, "id", None),
                getattr(request, "path", "?"),
            )
            return qs.none()

        return qs.filter(**{self.tenant_field: tenant})


class TenantOwnedDetailMixin(TenantQuerysetMixin):
    """
    Pour les vues qui retournent un objet (DetailView/UpdateView/DeleteView) :
    n'expose jamais un objet d'un autre tenant. ``get_object`` lève 404 si l'objet
    appartient à un autre tenant.
    """

    def get_object(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        obj = super().get_object(queryset=queryset)
        request_tenant = _request_tenant(self.request)

        if _user_is_platform_admin(self.request.user):
            return obj

        if request_tenant is None or getattr(obj, "tenant_id", None) != request_tenant.id:
            raise Http404
        return obj


# --------------------------------------------------------------------------- #
# Permissions DRF
# --------------------------------------------------------------------------- #
class HasTenantMembership(BasePermission):
    """
    L'utilisateur doit avoir un ``TenantUser`` actif sur le tenant courant.

    Les superusers passent toujours.
    """

    message = "Vous n'avez pas accès à cette organisation."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if _user_is_platform_admin(request.user):
            return True
        tenant = _request_tenant(request)
        if tenant is None:
            return False
        return bool(_membership(request.user, tenant))

    def has_object_permission(self, request, view, obj) -> bool:
        if _user_is_platform_admin(request.user):
            return True
        tenant = _request_tenant(request)
        if tenant is None:
            return False
        return getattr(obj, "tenant_id", None) == tenant.id


class HasTenantRole(HasTenantMembership):
    """
    Permission qui vérifie en plus la présence de rôles attendus.

    Sur le viewset / la vue, déclarer ::

        required_roles_safe = {"OWNER", "ADMIN", "MANAGER", "VIEWER", "MEMBER"}
        required_roles_write = {"OWNER", "ADMIN", "MANAGER"}

    ou un attribut unique ``required_roles`` (s'applique à toutes les méthodes).
    """

    def _expected_roles(self, view, request) -> Set[str]:
        if request.method in SAFE_METHODS:
            roles = getattr(view, "required_roles_safe", None)
        else:
            roles = getattr(view, "required_roles_write", None)
        if not roles:
            roles = getattr(view, "required_roles", set())
        return {str(r).upper() for r in (roles or [])}

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        expected = self._expected_roles(view, request)
        if not expected:
            return True
        if _user_is_platform_admin(request.user):
            return True
        return bool(expected & _user_roles(request))


class IsPlatformAdmin(BasePermission):
    """Réservé aux super-admins LYNEERP (RH externalisée, support…)."""

    def has_permission(self, request, view) -> bool:
        return _user_is_platform_admin(getattr(request, "user", None))


def assert_can_access_tenant(request, tenant) -> None:
    """
    Helper réutilisable hors DRF (par ex. dans un service métier) : lève
    PermissionDenied si l'utilisateur n'a pas accès au tenant donné.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise PermissionDenied("Authentification requise.")
    if _user_is_platform_admin(user):
        return
    if tenant is None or _membership(user, tenant) is None:
        raise PermissionDenied("Accès refusé à cette organisation.")
