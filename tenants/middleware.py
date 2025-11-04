# tenants/middleware.py
from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin
from tenants.models import Tenant
from urllib.parse import urlparse


class CurrentTenant:
    slug: str | None = None
    obj: Tenant | None = None


class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        slug = request.headers.get("X-Tenant-Id")
        if not slug:
            host = request.get_host().split(":")[0]
            parts = host.split(".")
            # ex: acme.lyneerp.com -> "acme"
            if len(parts) >= 3 and parts[-2:] == ["lyneerp", "com"]:
                slug = parts[0]
        # si auth déjà faite en amont, on peut lire request.auth (payload JWT)
        if not slug and hasattr(request, "auth") and isinstance(request.auth, dict):
            slug = request.auth.get("tenant_id")
        request.tenant = CurrentTenant()
        request.tenant.slug = slug
        if slug:
            try:
                request.tenant.obj = Tenant.objects.get(slug=slug)
            except Tenant.DoesNotExist:
                request.tenant.obj = None
