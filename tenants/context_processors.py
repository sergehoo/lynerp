"""
Context processors LYNEERP.

- ``current_tenant`` : expose ``request.tenant`` dans tous les templates
  (slug, id, instance).
- Expose aussi ``DEBUG`` pour permettre aux templates de basculer entre
  les CDN (pratique en dev) et les assets buildés localement (prod).
"""
from __future__ import annotations

from django.conf import settings


def current_tenant(request):
    tenant = getattr(request, "tenant", None)
    return {
        "current_tenant": tenant,
        "current_tenant_slug": getattr(tenant, "slug", None) if tenant else None,
        "current_tenant_id": str(getattr(tenant, "id", "")) if tenant else "",
        # Permet aux templates de faire `{% if DEBUG %} ... {% endif %}`
        # pour charger Tailwind/Alpine via CDN en dev.
        "DEBUG": bool(getattr(settings, "DEBUG", False)),
    }
