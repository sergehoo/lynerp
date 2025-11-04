# Lyneerp/tenant_filters.py
from rest_framework import viewsets


class TenantScopedQuerysetMixin:
    tenant_field = "tenant_id"

    def get_queryset(self):
        qs = super().get_queryset()
        slug = getattr(getattr(self.request, "tenant", None), "slug", None)
        return qs.none() if not slug else qs.filter(**{self.tenant_field: slug})

    def perform_create(self, serializer):
        slug = getattr(getattr(self.request, "tenant", None), "slug", None)
        serializer.save(**{self.tenant_field: slug})
