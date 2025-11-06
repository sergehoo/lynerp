#Lyneerp/hr/permissions.py

from rest_framework.permissions import BasePermission
import os, requests

LIC_URL = os.getenv("LICENSING_URL")
MODULE = os.getenv("MODULE_CODE", "rh")

LIC_TIMEOUT = float(os.getenv("LICENSING_TIMEOUT", "2.0"))
AUTO_ASSIGN = os.getenv("LICENSING_AUTO_ASSIGN", "1") == "1"  # auto-attribue un siège si dispo


class HasRHLicense(BasePermission):
    message = "Licence RH invalide ou expirée"

    def _check(self, tenant, user_sub, user_email):
        # 1) check user-level seat
        try:
            r = requests.get(
                f"{LIC_URL.rstrip('/')}/api/license/check",
                params={"tenant": tenant, "module": MODULE, "user_sub": user_sub},
                timeout=LIC_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json() or {}
                if data.get("active") and data.get("user_assigned", True):
                    return True, data
                # Plan actif mais user pas encore assigné
                if data.get("active") and not data.get("user_assigned") and AUTO_ASSIGN:
                    ar = requests.post(
                        f"{LIC_URL.rstrip('/')}/api/license/assign",
                        json={"tenant": tenant, "module": MODULE, "user_sub": user_sub, "email": user_email},
                        timeout=LIC_TIMEOUT,
                    )
                    if ar.status_code in (200, 201):
                        return True, ar.json() or {}
                    return False, {"detail": "Aucun siège disponible pour cet utilisateur."}
                return False, {"detail": "Licence active mais utilisateur non autorisé (siège non assigné)."}
            elif r.status_code in (402, 403):
                # 402 Payment Required (optionnel), 403 Forbidden
                try:
                    return False, r.json()
                except Exception:
                    return False, {"detail": "Licence RH invalide ou expirée"}
            else:
                return False, {"detail": f"Licensing service error {r.status_code}"}
        except Exception:
            return False, {"detail": "Service de licence indisponible"}

    def has_permission(self, request, view):
        tenant = request.headers.get("X-Tenant-Id")
        if not tenant or not LIC_URL:
            self.message = "Tenant manquant ou service de licence non configuré"
            return False

        payload = request.auth or {}
        user_sub = payload.get("sub") or getattr(getattr(request, "user", None), "id", None)
        user_email = payload.get("email") or payload.get("preferred_username") or getattr(request.user, "email", None)

        ok, info = self._check(tenant, user_sub, user_email)
        if not ok and info:
            # remonte le détail pour l'UI (ton base.html le lit déjà)
            self.message = info.get("detail") or self.message
            # Attacher sur request pour l’API/renderer si tu veux renvoyer {detail, code}
            setattr(request, "_license_error", info)
        return ok


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
