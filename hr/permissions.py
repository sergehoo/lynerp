#Lyneerp/hr/permissions.py
import base64
import json

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import BasePermission
import os, requests

from tenants.models import SeatAssignment, TenantUser, License, Tenant
from tenants.utils import resolve_tenant

LIC_URL = os.getenv("LICENSING_URL")
MODULE = os.getenv("MODULE_CODE", "rh")

LIC_TIMEOUT = float(os.getenv("LICENSING_TIMEOUT", "2.0"))
AUTO_ASSIGN = os.getenv("LICENSING_AUTO_ASSIGN", "1") == "1"  # auto-attribue un siège si dispo

USE_REMOTE = bool(os.getenv("LICENSING_URL"))


def _jwt_roles(request):
    p = getattr(request, "auth", {}) or {}
    realm = p.get("realm_access", {}).get("roles", [])
    client = p.get("resource_access", {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get("roles", [])
    return set(realm) | set(client)


def _parse_jwt_unverified(token: str):
    try:
        header, payload, _ = token.split(".")
        # base64url → base64
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return {}


def _sub_from_session(request):
    # OIDC_SESSION_KEY stocké par tes vues d’auth
    data = request.session.get(getattr(settings, "OIDC_SESSION_KEY", "oidc_user")) or {}
    # d’abord l’id_token si présent
    if data.get("id_token"):
        claims = _parse_jwt_unverified(data["id_token"])
        if claims.get("sub"):
            return claims["sub"]
    # sinon l’access_token
    if data.get("access_token"):
        claims = _parse_jwt_unverified(data["access_token"])
        if claims.get("sub"):
            return claims["sub"]
    # dernier recours : username/email (pas idéal mais évite un blocage dur)
    return (data.get("preferred_username") or data.get("email") or "").strip() or None


def _jwt_sub(request):
    # 1) Bearer vérifié par KeycloakJWTAuthentication
    payload = getattr(request, "auth", {}) or {}
    if payload.get("sub"):
        return payload["sub"]
    # 2) Fallback session OIDC (login côté serveur)
    return _sub_from_session(request)


def _local_status(tenant: Tenant, module: str, sub: str):
    from tenants.models import License, SeatAssignment
    from datetime import date
    lic = (License.objects
           .filter(tenant=tenant, module=module, active=True, valid_until__gte=date.today())
           .order_by("-valid_until").first())
    if not lic:
        return {"active": False}
    seats_used = SeatAssignment.objects.filter(tenant=tenant, module=module, active=True).count()
    user_entitled = SeatAssignment.objects.filter(tenant=tenant, module=module, user_sub=sub, active=True).exists()
    return {
        "active": True,
        "plan": lic.plan,
        "valid_until": lic.valid_until,
        "seats_total": lic.seats,
        "seats_used": seats_used,
        "user_entitled": user_entitled,
        "jit_allowed": seats_used < lic.seats,
        "license_id": str(lic.id),
    }


def _jit_assign_local(tenant: Tenant, module: str, sub: str, email: str):
    from hr.auth_utils import ensure_seat_for_user
    return ensure_seat_for_user(tenant, module, sub, email or "")


class HasRHAccess(BasePermission):
    message = "Accès RH non autorisé."

    def has_permission(self, request, view):
        # Vérification basique d'authentification
        if not request.user.is_authenticated:
            self.message = "Utilisateur non authentifié"
            return False

        # Résolution du tenant
        tenant_id = (request.headers.get("X-Tenant-Id") or
                     getattr(request, "tenant_id", None) or
                     request.session.get("tenant_id"))

        if not tenant_id:
            self.message = "Tenant introuvable"
            return False

        tenant_obj = resolve_tenant(tenant_id)
        if not tenant_obj:
            self.message = "Tenant introuvable"
            return False

        # Vérification licence (version simplifiée pour debug)
        try:
            today = timezone.now().date()
            lic = License.objects.filter(
                tenant=tenant_obj,
                module=MODULE_CODE,
                active=True,
                valid_until__gte=today
            ).first()

            if not lic:
                self.message = "Licence RH non trouvée ou expirée"
                return False

        except Exception as e:
            self.message = f"Erreur vérification licence: {str(e)}"
            return False

        return True


MODULE_CODE = "rh"  # ou settings.MODULE_CODE


class HasRHSeatAndLicense(BasePermission):
    message = "Accès RH refusé (licence invalide, siège non attribué ou rôle insuffisant)."
    required_roles = []  # ex: ["hr:view"] ou ["hr:manage"]

    def has_permission(self, request, view):
        tenant_id = request.session.get("tenant_id") or request.headers.get("X-Tenant-Id")
        if not tenant_id or not request.user.is_authenticated:
            return False

        # 1) Charger tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return False

        # 2) Vérifier appartenance au tenant
        if not TenantUser.objects.filter(
                tenant=tenant, user=request.user, is_active=True
        ).exists():
            return False

        # 3) Licence valide
        today = timezone.now().date()
        try:
            lic = License.objects.get(
                tenant=tenant, module=MODULE_CODE, active=True, valid_until__gte=today
            )
        except License.DoesNotExist:
            return False

        # 4) Siège attribué à l’utilisateur (via sub)
        payload = request.auth or {}
        sub = payload.get("sub") or payload.get("user_id")  # selon ton token
        if not sub:
            return False

        seat = SeatAssignment.objects.filter(
            tenant=tenant, module=MODULE_CODE, user_sub=sub, active=True
        ).select_related("license").first()

        if not seat:
            return False

        # Optionnel : sécurité forte → le siège doit pointer la même licence
        if seat.license_id and seat.license_id != lic.id:
            return False

        # 5) Rôles
        need = getattr(view, "required_roles", getattr(self, "required_roles", []))
        if need:
            roles = (payload.get("realm_access", {}).get("roles", [])
                     + payload.get("resource_access", {}).get("rh-core", {}).get("roles", []))
            if not all(r in roles for r in need):
                return False

        return True


class HasRole(BasePermission):
    message = "Rôle insuffisant"

    def has_permission(self, request, view):
        # Si pas de rôles requis, autoriser
        required_roles = getattr(view, 'required_roles', [])
        if not required_roles:
            return True

        # Récupération des rôles depuis JWT ou session
        roles = set()

        # Depuis JWT
        if hasattr(request, 'auth') and request.auth:
            payload = request.auth
            roles.update(payload.get("realm_access", {}).get("roles", []))
            roles.update(payload.get("resource_access", {}).get("rh-core", {}).get("roles", []))

        # Depuis session OIDC
        oidc_data = request.session.get(getattr(settings, "OIDC_SESSION_KEY", "oidc_user"), {})
        if oidc_data.get("roles"):
            roles.update(oidc_data["roles"])

        return all(role in roles for role in required_roles)
