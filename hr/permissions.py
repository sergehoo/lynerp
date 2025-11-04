from rest_framework.permissions import BasePermission
import os, requests

LIC_URL = os.getenv("LICENSING_URL")
MODULE = os.getenv("MODULE_CODE", "rh")


class HasRHLicense(BasePermission):
    message = "Licence RH invalide ou expirée"

    def has_permission(self, request, view):
        tenant = request.headers.get("X-Tenant-Id")
        if not tenant or not LIC_URL:
            return False
        try:
            r = requests.get(LIC_URL, params={"tenant": tenant, "module": MODULE}, timeout=2)
            return r.status_code == 200 and r.json().get("active", False)
        except Exception:
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
