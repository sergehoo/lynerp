#Lyneerp/hr/permissions.py
from django.conf import settings
from rest_framework.permissions import BasePermission
import os, requests

LIC_URL = os.getenv("LICENSING_URL")
MODULE = os.getenv("MODULE_CODE", "rh")

LIC_TIMEOUT = float(os.getenv("LICENSING_TIMEOUT", "2.0"))
AUTO_ASSIGN = os.getenv("LICENSING_AUTO_ASSIGN", "1") == "1"  # auto-attribue un siège si dispo

USE_REMOTE = bool(os.getenv("LICENSING_URL"))


def _jwt_sub(request):
    payload = getattr(request, "auth", {}) or {}
    return payload.get("sub")


def _jwt_roles(request):
    p = getattr(request, "auth", {}) or {}
    realm = p.get("realm_access", {}).get("roles", [])
    client = p.get("resource_access", {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get("roles", [])
    return set(realm) | set(client)


def _local_status(tenant, module, sub):
    # Appelle la vue interne ou interroge le modèle directement
    from tenants.models import License, SeatAssignment
    from datetime import date
    lic = License.objects.filter(tenant=tenant, module=module).order_by("-valid_until").first()
    if not lic:
        return {"active": False}

    active = lic.active and lic.valid_until and lic.valid_until >= date.today()
    if not active:
        return {"active": False}
    seats_used = SeatAssignment.objects.filter(tenant=tenant, module=module, active=True).count()
    user_entitled = SeatAssignment.objects.filter(tenant=tenant, module=module, user_sub=sub, active=True).exists()
    return {
        "active": True,
        "plan": lic.plan, "valid_until": lic.valid_until,
        "seats_total": lic.seats, "seats_used": seats_used,
        "user_entitled": user_entitled,
        "jit_allowed": seats_used < lic.seats
    }


class HasRHAccess(BasePermission):
    message = "Accès RH non autorisé (licence/siège/rôle)."
    required_roles = {"rh:use"}  # Override possible sur la View via `required_roles = {...}`

    def has_permission(self, request, view):
        tenant = request.headers.get("X-Tenant-Id")
        if not tenant:
            self.message = "X-Tenant-Id manquant"
            return False

        sub = _jwt_sub(request)
        if not sub:
            self.message = "Token invalide (sub manquant)"
            return False

        # 1) Rôles
        need = set(getattr(view, "required_roles", self.required_roles))
        if not need.issubset(_jwt_roles(request)):
            self.message = "Rôle insuffisant"
            return False

        # 2) Licence &siège
        try:
            if USE_REMOTE:
                r = requests.get(f"{LIC_URL}/status", params={"tenant": tenant, "module": MODULE, "user_sub": sub},
                                 timeout=3)
                if r.status_code != 200:
                    self.message = "Service licence indisponible"
                    return False
                data = r.json()
            else:
                data = _local_status(tenant, MODULE, sub)

            if not data.get("active"):
                self.message = "Licence RH invalide ou expirée"
                return False

            if data.get("user_entitled"):
                return True

            if data.get("jit_allowed"):
                # Claim auto
                if USE_REMOTE:
                    cr = requests.post(f"{LIC_URL}/claim-seat",
                                       json={"tenant": tenant, "module": MODULE, "user_sub": sub}, timeout=3)
                    if cr.status_code == 200 and cr.json().get("user_entitled"):
                        return True
                    self.message = cr.json().get("detail", "Aucun siège disponible")
                    return False
                else:
                    # Local claim
                    from tenants.models import SeatAssignment
                    from django.utils import timezone
                    SeatAssignment.objects.get_or_create(
                        tenant=tenant, module=MODULE, user_sub=sub,
                        defaults={"active": True, "activated_at": timezone.now()}
                    )
                    return True

            self.message = "Aucun siège assigné à cet utilisateur"
            return False
        except Exception:
            self.message = "Erreur vérification licence"
            return False


class HasRole(BasePermission):
    required = []  # ex: ["hr:view"] ou ["hr:manage"]
    message = "Rôle insuffisant"

    def has_permission(self, request, view):
        payload = request.auth or {}
        roles = payload.get("realm_access", {}).get("roles", []) + payload.get("resource_access", {}).get("rh-core",
                                                                                                          {}).get(
            "roles", [])
        need = getattr(view, "required_roles", getattr(self, "required", []))
        return all(r in roles for r in need)
