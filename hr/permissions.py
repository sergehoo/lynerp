# Lyneerp/hr/permissions.py
"""
Permissions RH sans vérification de licence/siège.

- Aucune requête n'est bloquée à cause d'une licence.
- Contrôle par rôles Keycloak (facultatif) si la vue définit `required_roles`.
- Compatible JWT (Authorization: Bearer) et session OIDC (whoami via SessionAuthentication).
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import BasePermission


# --- Helpers -----------------------------------------------------------------

def _jwt_roles(request) -> set[str]:
    """
    Récupère les rôles (realm + client) depuis le payload JWT vérifié par
    votre authenticator (request.auth) ou, à défaut, renvoie un set() vide.
    """
    p = getattr(request, "auth", {}) or {}
    client_id = getattr(settings, "KEYCLOAK_CLIENT_ID", "rh-core")
    realm = p.get("realm_access", {}).get("roles", []) or []
    client = p.get("resource_access", {}).get(client_id, {}).get("roles", []) or []
    return set(realm) | set(client)


def _session_roles(request) -> set[str]:
    """
    Optionnel : si vous stockez la liste 'roles' en session OIDC, on les ajoute.
    """
    key = getattr(settings, "OIDC_SESSION_KEY", "oidc_user")
    data = request.session.get(key, {}) or {}
    roles = data.get("roles") or []
    return set(roles)


def _all_roles(request) -> set[str]:
    """
    Union des rôles issus du JWT et (optionnellement) de la session OIDC.
    """
    return _jwt_roles(request) | _session_roles(request)


def _license_enforcement_enabled() -> bool:
    """
    Flag global. Par défaut désactivé (False) pour éviter toute surprise.
    """
    return bool(getattr(settings, "LICENSE_ENFORCEMENT", False))


# --- Permissions -------------------------------------------------------------

class HasRHAccess(BasePermission):
    """
    Permission d'accès RH GENERIQUE.

    - Si `required_roles` est défini sur la vue, on vérifie ces rôles.
    - AUCUNE vérification de licence/siège n'est réalisée.
    - On n'impose PAS la présence d'un tenant ici (la logique tenant peut
      être gérée par vos middlewares et vos queryset/filters).
    """
    message = "Accès RH non autorisé."
    required_roles: set[str] = set()  # Exemple: {"rh:use"} si vous voulez un rôle minimal

    def has_permission(self, request, view) -> bool:
        # 1) Contrôle par rôles (facultatif)
        need = set(getattr(view, "required_roles", self.required_roles))
        if need and not need.issubset(_all_roles(request)):
            self.message = "Rôle insuffisant"
            return False

        # 2) Licence (désactivée)
        # Si un jour vous réactivez la licence globalement, vous pourrez
        # remettre ici vos vérifications. Pour l’instant, on autorise.
        if not _license_enforcement_enabled():
            return True

        # (Si vous remettez ENFORCEMENT=True un jour, implémentez ci-dessous)
        return True


class HasRHSeatAndLicense(BasePermission):
    """
    Ancienne permission stricte licence/siège.
    -> Devient un NO-OP quand LICENSE_ENFORCEMENT == False.
    -> Peut garder un contrôle par rôles si la vue le demande.
    """
    message = "Accès RH refusé."
    required_roles: list[str] = []

    def has_permission(self, request, view) -> bool:
        # Désactivation totale des licences
        if not _license_enforcement_enabled():
            need = set(getattr(view, "required_roles", getattr(self, "required_roles", [])))
            if need:
                return need.issubset(_all_roles(request))
            return True

        # (Si vous remettez ENFORCEMENT=True, implémentez ici licence/siège)
        return True


class HasRole(BasePermission):
    """
    Mini-permission utilitaire : autorise si TOUS les rôles requis sont présents.
    Si la vue ne définit pas `required_roles`, on autorise.
    """
    message = "Rôle insuffisant"

    def has_permission(self, request, view) -> bool:
        need = set(getattr(view, 'required_roles', []))
        if not need:
            return True
        return need.issubset(_all_roles(request))


class IsSuperAdminOrTenantAdmin(BasePermission):
    """
    - Super Admin (structure RH externalisée) : accès à tous les tenants
    - Admin entreprise : accès uniquement à son tenant
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # si super admin -> tout ok
        if request.user.is_superuser or request.user.groups.filter(name="SUPER_ADMIN").exists():
            return True

        # sinon -> doit matcher tenant
        tenant = getattr(request, "tenant_id", None) or request.headers.get("X-Tenant-Id")
        return getattr(obj, "tenant_id", None) == tenant
