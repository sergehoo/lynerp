"""
Permissions DRF pour le module IA.

- ``CanUseAI`` : accès basique au chat (tout TenantUser actif).
- ``CanApproveAIAction`` : approuver/rejeter une AIAction (rôles élevés).
- ``CanRunDestructiveAITool`` : déclencher un outil destructif (très restrictif).
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from Lyneerp.core.permissions import (
    HasTenantMembership,
    _user_is_platform_admin,
    _membership,
    _request_tenant,
)


APPROVAL_ROLES = {"OWNER", "ADMIN", "MANAGER", "HR_BPO"}
DESTRUCTIVE_ROLES = {"OWNER", "ADMIN"}


class CanUseAI(HasTenantMembership):
    """N'importe quel membre actif d'un tenant peut utiliser le chat."""

    message = "Vous n'avez pas accès à l'assistant IA."


class CanApproveAIAction(BasePermission):
    """
    Réservé aux rôles ``OWNER``, ``ADMIN``, ``MANAGER`` ou ``HR_BPO`` (et
    superusers globaux). Un utilisateur ne peut pas approuver l'action qu'il
    a lui-même proposée (séparation des privilèges).
    """

    message = "Vous n'avez pas le droit d'approuver les actions IA."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if _user_is_platform_admin(request.user):
            return True
        tenant = _request_tenant(request)
        m = _membership(request.user, tenant)
        if m is None:
            return False
        return m.role.upper() in APPROVAL_ROLES

    def has_object_permission(self, request, view, obj) -> bool:
        if not self.has_permission(request, view):
            return False
        # Empêche l'auto-approbation.
        if (
            getattr(obj, "proposed_by_id", None)
            and obj.proposed_by_id == request.user.id
            and not _user_is_platform_admin(request.user)
        ):
            self.message = (
                "Vous ne pouvez pas approuver une action que vous avez vous-même "
                "déclenchée."
            )
            return False
        return True


class CanRunDestructiveAITool(BasePermission):
    """Pour déclencher un outil noté ``destructive`` (rares)."""

    message = "Action IA destructive réservée aux administrateurs."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if _user_is_platform_admin(request.user):
            return True
        tenant = _request_tenant(request)
        m = _membership(request.user, tenant)
        if m is None:
            return False
        return m.role.upper() in DESTRUCTIVE_ROLES
